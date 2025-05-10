""" validate E-Ing GML document """
import os.path
from qgis.PyQt.QtWidgets import QMessageBox

from .gml_importer import GmlImporter

class GmlValidator():
    """ validator class for E-Ing GML """

    MESSAGE_TAG = 'GML validation'

    def __init__(self, iface, tr):
        """ initialize """
        self.iface = iface
        self.tr = tr
        self.plugin_dir = os.path.dirname(__file__)

    def validate_gml(self, gml_path):
        """ validate a gml doc 

            :param gml_path: path to gml file
        """
        try:
            from lxml import etree
        except ModuleNotFoundError:
            QMessageBox.critical(None, self.tr("CRITICAL error"),
                                 self.tr("Python lxml package not found, please install it."))
            return

        importer = GmlImporter(self.iface)
        importer.import_gml_metadata_to_gpkg(gml_path)
        #gml_data_source = ogr.GetDriverByName('gml').Open(gml_path)
        name = f"eing_{importer.xsd_version}.xsd"
        xsd_path = os.path.join(self.plugin_dir, "xsds", name)
        # load and prepare schema
        try:
            xmlschema_doc = etree.parse(xsd_path)
        except OSError:
            QMessageBox.critical(None, self.tr("CRITICAL error"),
                                 self.tr("Schema not found: ") + xsd_path)
            return
        try:
            xmlschema = etree.XMLSchema(xmlschema_doc)
        except etree.XMLSchemaParseError as e:
            QMessageBox.critical(None, self.tr("CRITICAL error"),
                                 self.tr("Error in schema: ") + str(e))
            return
        etree.clear_error_log()
        try:
            doc = etree.parse(gml_path)
        except (OSError, etree.XMLSyntaxError):
            QMessageBox.critical(None, self.tr("CRITICAL error"),
                                 self.tr("Invalid or missing GML file: ") + gml_path)
            return

        valid = xmlschema.validate(doc)
        if not valid:
            QMessageBox.critical(None, self.tr("ERROR"),
                              self.tr("Error in GML: ") + str(xmlschema.error_log.last_error))
            return
        QMessageBox.information(None, self.tr("INFO"),
                                gml_path + self.tr(" is valid to : ") + name) 
