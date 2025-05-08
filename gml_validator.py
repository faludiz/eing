""" validate E-Ing GML document """
import os.path
from lxml import etree
from osgeo import ogr
from qgis.core import Qgis, QgsMessageLog

from .gml_importer import GmlImporter

class GmlValidator():
    """ validator class for E-Ing GML """

    MESSAGE_TAG = 'GML validation'

    def __init__(self, iface):
        """ initialize """
        self.iface = iface

    def validate_gml(self, gml_path, plugin_dir):
        """ validate a gml doc 

            :param gml_path: path to gml file
            :param plugin_dir: path to plugin folder
        """
        ogr.UseExceptions()
        # GML to validate

        importer = GmlImporter(self.iface)
        importer.import_gml_metadata_to_gpkg(gml_path)
        gml_data_source = ogr.GetDriverByName('gml').Open(gml_path)
        name = f"eing_{importer.xsd_version}.xsd"
        xsd_path = os.path.join(plugin_dir, "xsds", name)
        # load and prepare schema
        try:
            xmlschema_doc = etree.parse(xsd_path)
        except OSError:
            QgsMessageLog.logMessage("Schema not found: " + xsd_path,
                                     GmlValidator.MESSAGE_TAG,
                                     level = Qgis.Critical)
            return
        try:
            xmlschema = etree.XMLSchema(xmlschema_doc)
        except etree.XMLSchemaParseError as e:
            QgsMessageLog.logMessage("Error in Schema: " + e,
                                     GmlValidator.MESSAGE_TAG,
                                     level = Qgis.Critical)
        etree.clear_error_log()
        try:
            doc = etree.parse(gml_path)
        except (OSError, etree.XMLSyntaxError):
            QgsMessageLog.logMessage("Invalid or missing GML file: " + gml_path,
                                     GmlValidator.MESSAGE_TAG,
                                     level = Qgis.Critical)
            return

        valid = xmlschema.validate(doc)
        if not valid:
            QgsMessageLog.logMessage("Error in GML: " +
                                     str(xmlschema.error_log.last_error),
                                     GmlValidator.MESSAGE_TAG,
                                     level = Qgis.Critical)
            return
        QgsMessageLog.logMessage("GML is valid", GmlValidator.MESSAGE_TAG,
                                 level = Qgis.Critical)
