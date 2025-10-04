# -*- coding: utf-8 -*-

""" Export non empty layers from GeoPackage to GML """

import os
from xml.etree.ElementTree import Element, SubElement, ElementTree
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtCore import QCoreApplication
from osgeo import ogr

class GmlExporter:
    """GeoPackage --> GML exporter"""

    MESSAGE_TAG = 'GML export'

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

    def tr(self, message):
        return QCoreApplication.translate('GmlExporter', message)

    def format_float(self, number):
        """ remove trailing zeros """
        wstr = f"{number:.3f}"
        return wstr.rstrip('0').rstrip('.')
#        return str('{0:.3f}'.format(number)).rstrip('0').rstrip('.')

    def add_geometry_element(self, layer_element, geom):
        """ Add a feature to GML structure """
        geom_element = SubElement(layer_element, 'eing:geometry')
        geom_name = geom.GetGeometryName()

        if geom_name == 'POINT':
            point_element = SubElement(geom_element, 'gml:Point', {'srsDimension': '2', 'srsName': 'urn:x-ogc:def:crs:EPSG:23700' })
            gml_pos_element = SubElement(point_element, 'gml:pos')
            gml_pos_element.text = self.format_float(geom.GetX()) + ' ' + \
                                   self.format_float(geom.GetY())
        elif geom_name == 'POLYGON':
            polygon_element = SubElement(geom_element, 'gml:Polygon',
                                         {'srsDimension': '2',
                                          'srsName': 'urn:x-ogc:def:crs:EPSG:23700' })

            for ring_index in range(geom.GetGeometryCount()):
                gml_exterior_element = SubElement(polygon_element,
                                                  'gml:exterior' if ring_index == 0 else 'gml:interior')
                gml_linear_ring_element = SubElement(gml_exterior_element,
                                                     'gml:LinearRing', {'srsDimension': '2' })
                gml_pos_list_element = SubElement(gml_linear_ring_element,
                                                  'gml:posList')
                ring = geom.GetGeometryRef(ring_index)

                point_arr = []
                for i in range(0, ring.GetPointCount()):
                    eov_x, eov_y = ring.GetPoint_2D(i)
                    point_arr.append(self.format_float(eov_x) + ' ' + self.format_float(eov_y))

                gml_pos_list_element.text = ' '.join(point_arr)

        elif geom_name == 'LINESTRING':
            linestring_element = SubElement(geom_element, 'gml:LineString', {'srsDimension': '2', 'srsName': 'urn:x-ogc:def:crs:EPSG:23700' })
            gml_pos_list_element = SubElement(linestring_element, 'gml:posList')

            point_arr = []
            for i in range(geom.GetPointCount()):
                eov_x, eov_y = geom.GetPoint_2D(i)
                point_arr.append(self.format_float(eov_x) + ' ' + self.format_float(eov_y))

            gml_pos_list_element.text = ' '.join(point_arr)

        else:
            raise Exception(self.tr("Unsupported geometry type: ") + geom_name)

    def add_field_elements(self, layer_element, gml_feature, gml_layer_def, new_fid):
        """ Adding feature attributes as nodes """
        for i in range(gml_layer_def.GetFieldCount()):
            field_name = gml_layer_def.GetFieldDefn(i).GetName()
            field_val = gml_feature.GetField(field_name)

            if field_name == 'GEOBJ_ID':
                layer_element.set('gml:id', 'fid-' + str(new_fid if field_val is None else field_val))

            field_element = SubElement(layer_element, 'eing:' + field_name)

            # remove ".0" part for floats
            if isinstance(field_val, float):
                field_element.text = self.format_float(field_val)

            elif field_val is not None:
                field_element.text = str(field_val)

    def add_metadata_list_element(self, gpkg_data_source, meta_data_key,
                                  meta_data_list_element):
        """ add metatadata from gpkg to GML """
        meta_data_value = gpkg_data_source.GetMetadataItem(meta_data_key)
        meta_data_element = SubElement(meta_data_list_element, meta_data_key)
        meta_data_element.text = meta_data_value

    def add_metadata_element(self, root, gpkg_data_source):
        """ create metaDataProperty node and fill it 0from GeoPackage meta data """
        meta_data_list_element = SubElement(SubElement(SubElement(root, 'gml:metaDataProperty'), 'gml:GenericMetaData'), 'MetaDataList')

        self.add_metadata_list_element(gpkg_data_source, 'gmlID', meta_data_list_element)
        self.add_metadata_list_element(gpkg_data_source, 'gmlExportDate', meta_data_list_element)
        self.add_metadata_list_element(gpkg_data_source, 'gmlGeobjIds', meta_data_list_element)
        self.add_metadata_list_element(gpkg_data_source, 'xsdVersion', meta_data_list_element)

    def add_envelope_element(self, root, extent):
        """ Add bounding box """
        bounded_by_element = SubElement(root, 'gml:boundedBy')
        envelope_element = SubElement(bounded_by_element, 'gml:Envelope', { 'srsDimension': '2', 'srsName': 'urn:x-ogc:def:crs:EPSG:23700' })

        lower_corner_element = SubElement(envelope_element, 'gml:lowerCorner')
        lower_corner_element.text = self.format_float(extent[0]) + " " + self.format_float(extent[2])

        upper_corner_element = SubElement(envelope_element, 'gml:upperCorner')
        upper_corner_element.text = self.format_float(extent[1]) + " " + self.format_float(extent[3])

    def get_sorted_layer_indexes(self, gpkg_data_source):
        """
            returns the layer list in the order neccesary in GML
            :param gpkg_data_source: GeoPackage source
            :return: sorted list of layer indices from data source
        """
        indexes = []

        for layer_index in range(gpkg_data_source.GetLayerCount()):
            gpkg_layer = gpkg_data_source.GetLayerByIndex(layer_index)

            if gpkg_layer.GetFeatureCount() > 0:
                try:
                    indexes.append((gpkg_layer.GetNextFeature().GetField('RETEG_ID'), layer_index))
                except KeyError:
                    pass    # simple skip extra tables
                    # TODO it would be better if only XSD layers were added
                gpkg_layer.ResetReading()

        indexes.sort(reverse = True)

        return list(map(lambda x: x[1], indexes))

    def export_to_gml(self, gpkg_path, gml_path):
        """ Export features from GeoPackage to GML """
        ogr.UseExceptions()

        try:
            gpkg_data_source = ogr.GetDriverByName('gpkg').Open(gpkg_path)
        except:
            QMessageBox.critical(None, self.tr("CRITICAL error"),
                                 self.tr("Cannot open GeoPackage: ") + gpkg_path)
            return
        
        try:
            with open(gml_path, 'a'):
                pass
        except:
            QMessageBox.critical(None, self.tr("CRITICAL error"), self.tr("Cannot write to GML file: ") + gml_path)
            return

        root = Element('gml:FeatureCollection')
        root.set('xmlns:eing', 'eing.foldhivatal.hu')
        root.set('xmlns:gml', 'http://www.opengis.net/gml')

        # add metadata nodes
        self.add_metadata_element(root, gpkg_data_source)
        feature_members_element = SubElement(root, 'gml:featureMembers')

        new_fid = 1

        for layer_index in self.get_sorted_layer_indexes(gpkg_data_source):
            gpkg_layer = gpkg_data_source.GetLayerByIndex(layer_index)
            layer_name = gpkg_layer.GetName()

            # copy features from gpkg to GML
            for feature in gpkg_layer:
                layer_element = SubElement(feature_members_element,
                                           'eing:' + layer_name)
                # add envelope node
                self.add_envelope_element(layer_element,
                                          feature.GetGeometryRef().GetEnvelope())
                # add field node
                self.add_field_elements(layer_element, feature,
                                        gpkg_layer.GetLayerDefn(), new_fid)
                # add geometry node
                self.add_geometry_element(layer_element,
                                          feature.GetGeometryRef())
                new_fid += 1

        tree = ElementTree(root)
        tree.write(gml_path, xml_declaration = True, encoding = 'UTF-8')

        QMessageBox.information(None, self.tr("INFO"),
                                self.tr("Succesful GML export"))
