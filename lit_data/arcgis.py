from __future__ import annotations
from enum import Enum
from urllib.parse import urljoin, urlparse
from io import StringIO
import requests
import csv
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36"  # noqa: E501
}

PARAMS = {"f": "json"}


class ArcObject:
    def __init__(self, url: str, headers=HEADERS, params=PARAMS):
        self._headers = headers
        self._params = params
        self._url: str = urljoin(url, urlparse(url).path)  # removes url query parameters
        self._data: dict = {}

    @property
    def url(self):
        return self._url

    @property
    def data(self):
        return self._data

    def get(self) -> ArcObject:
        r = requests.get(self._url, headers=self._headers, params=self._params)
        r.raise_for_status()
        self._data = r.json()

        return self

    def __str__(self):
        return self._url


class ArcDirectory(ArcObject):
    def __init__(self, url: str):
        super().__init__(url)

        self._folders: dict[str, ArcFolder] = {}
        self._services: dict[str, ArcService] = {}

    def folders(self, name: str = None) -> dict[str, ArcFolder] | ArcFolder:
        if not self._folders:
            for name_ in self.data.get("folders", []):
                self._folders[name_] = ArcFolder(urljoin(self.url, name_), name_)

        if name is not None:
            return self._folders[name]
        else:
            return self._folders

    def services(self, name: str = None) -> dict[str, ArcService] | ArcService:
        if not self._services:
            for service in self.data.get("services", []):
                self._services[service["name"]] = ArcService.from_dict(service)

        if name is not None:
            return self._services[name]
        else:
            return self._services


class ArcServer(ArcDirectory):
    def __init__(self, url: str):
        super().__init__(url)
        self.get()


class ArcFolder(ArcDirectory):
    def __init__(self, url: str, name: str):
        super().__init__(url)
        self.name: str = name

    def __str__(self):
        return self.name


class ArcService(ArcObject):
    def __init__(self, url: str, name: str, type: ArcServiceType):
        super().__init__(url)
        self._name: str = name
        self._service_type: ArcServiceType = type
        self._layers: dict[str, ArcLayer] = {}
        self._tables: dict[str, ArcTable] = {}

        if self.service_type != ArcServiceType.FEATURE_SERVER:
            raise NotImplementedError("Only feature services are supported")

    @property
    def name(self):
        return self._name

    @property
    def service_type(self):
        return self._service_type

    @classmethod
    def from_dict(cls, data: dict) -> ArcService:
        return cls(data["url"], data["name"], ArcServiceType(data["type"]))

    @classmethod
    def from_url(cls, url: str) -> ArcService:
        path = urlparse(url).path.strip("/").split("/")
        return cls(url, path[-2], ArcServiceType(path[-1]))

    def layers(self, id: int = None) -> dict[str, ArcLayer] | ArcLayer:
        if not self.data:
            self.get()

        if not self._layers:
            for layer in self.data.get("layers"):
                self._layers[layer["id"]] = ArcLayer.from_dict(self.url, layer)

        if id is not None:
            return self._layers[id]
        else:
            return self._layers

    def tables(self, id: int = None) -> dict[str, ArcTable] | ArcTable:
        if not self.data:
            self.get()

        if not self._tables:
            for table in self.data.get("tables"):
                self._tables[table["id"]] = ArcTable.from_dict(self.url, table)

        if id is not None:
            return self._tables[id]
        else:
            return self._tables

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"ArcService({self.name}, {self.service_type})"


class ArcLayer(ArcObject):
    def __init__(self, url: str, id: int, type: ArcLayerType):
        super().__init__(url)
        self._id: int = id
        self._layer_type: ArcLayerType = type

    @property
    def id(self):
        return self._id

    @property
    def layer_type(self):
        return self._layer_type

    def query(self, query):
        raise NotImplementedError("Layer query not yet implemented")

    @classmethod
    def from_dict(cls, url: str, data: dict) -> ArcLayer:
        return cls(f"{url}/{data['id']}", data["id"], ArcLayerType(data["type"]))

    def __repr__(self):
        return f"ArcLayer({self.id}, {self.layer_type})"


class ArcTable(ArcObject):
    def __init__(self, url: str, id: int, name: str):
        super().__init__(url)
        self._id: int = id
        self._name: str = name
        self._fields: dict[str, ArcField] = {}
        self._record_count: int = None

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    def fields(self) -> dict[str, ArcField]:
        if not self.data:
            self.get()

        if not self._fields:
            self._fields = {field["name"]: ArcField.from_dict(field) for field in self.data["fields"]}

        return self._fields

    def record_count(self) -> int:
        if not self.data:
            self.get()

        if not self._record_count:
            self._record_count = self.data["standardMaxRecordCount"]

        return self._record_count

    @classmethod
    def from_dict(cls, url: str, data: dict) -> ArcTable:
        return cls(f"{url}/{data['id']}", data["id"], data["name"])

    def _query_json(self, params: dict) -> dict:
        r = requests.get(f"{self.url}/query", headers=self._headers, params=params)
        r.raise_for_status()
        return r.json()

    def query(
        self,
        where: str = "1=1",
        offset: int = 0,
        record_count: int = None,
        order_by: str = None,
        out: str = "*",
        result_type: str = "standard",
        all: bool = False,  # all = True with a huge dataset could take forever
    ) -> ArcData:
        if all and (record_count or offset):
            raise ValueError("all=True cannot be used with offset or record_count")

        params = {
            "where": where,
            "resultOffset": offset,
            "resultRecordCount": record_count if record_count else self.record_count(),
            "orderByFields": order_by,
            "outFields": out,
            "resultType": result_type,
        } | self._params
        result = self._query_json(params)

        if all and result["features"]:
            done = False
            while not done:
                query = self._query_json(params)
                if query["features"]:
                    result["features"] += query["features"]
                    params["resultOffset"] += params["resultRecordCount"]
                else:
                    done = True

        return ArcData.from_json(result)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"ArcTable({self.id}, {self.name})"


class ArcField:
    def __init__(self, name: str, type: ArcFieldType, alias: str = None):
        self._name: str = name
        self._field_type: ArcFieldType = type
        self._alias: str = alias if alias else name

    @property
    def name(self):
        return self._name

    @property
    def alias(self):
        return self._alias

    @property
    def field_type(self):
        return self._field_type

    @classmethod
    def from_dict(cls, data: dict) -> ArcField:
        return cls(data["name"], ArcFieldType(data["type"]), data["alias"])

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"ArcField({self.name}, {self.field_type})"


class ArcData:
    def __init__(self, fields: dict[str, ArcField], features: list[dict]):
        self._fields: dict[str, ArcField] = fields
        self._features: list[dict] = features

    @property
    def fields(self):
        return self._fields

    @property
    def features(self):
        return self._features

    def _format_value(self, field_name: str, value):
        raise NotImplementedError("Field value formatting not yet implemented")

    def _write_csv(self, to):
        writer = csv.DictWriter(to, fieldnames=self._fields.keys())
        writer.writeheader()

        for feature in self.features:
            writer.writerow(feature)

        return to

    def format(self) -> ArcData:
        raise NotImplementedError("Field formatting not yet implemented")

    def json(self, filename: str = None, indent: int = 2):
        if filename:
            with open(filename, "w") as f:
                json.dump(self.features, f, indent=indent)
        else:
            return json.dumps(self.features)

    def csv(self, filename: str = None):
        if filename:
            with open(filename, "w") as f:
                self._write_csv(f)
        else:
            return self._write_csv(StringIO()).getvalue()

    @classmethod
    def from_json(cls, data: dict) -> ArcData:
        return cls(
            {field["name"]: ArcField.from_dict(field) for field in data["fields"]},
            [feature["attributes"] for feature in data["features"]],
        )


# Generated by Copilot, IT KNOWS ALL
class ArcServiceType(str, Enum):
    """
    ArcGIS service types
    """

    MAP_SERVER = "MapServer"
    FEATURE_SERVER = "FeatureServer"
    GEODATABASE = "GeoDatabase"
    GEOCODING = "Geocoding"
    GEOMETRY_SERVER = "GeometryServer"
    IMAGE_SERVER = "ImageServer"
    TILE_SERVER = "TileServer"
    GEOPROCESSING = "Geoprocessing"
    GEODATA_ACCESS = "GeodataAccess"
    GEOCODE_SERVER = "GeocodeServer"
    GEOMETRY_ANALYTICS = "GeometryAnalytics"
    GEOMETRY_SERVICE = "GeometryService"
    GEOMETRY_TOOLS = "GeometryTools"
    GEOMETRY_TOOLS_ADMIN = "GeometryToolsAdmin"
    GEOMETRY_TOOLS_ANALYTICS = "GeometryToolsAnalytics"
    GEOMETRY_TOOLS_GEOCODING = "GeometryToolsGeocoding"
    GEOMETRY_TOOLS_GEODATA_ACCESS = "GeometryToolsGeodataAccess"
    GEOMETRY_TOOLS_GEOMETRY_ANALYTICS = "GeometryToolsGeometryAnalytics"
    GEOMETRY_TOOLS_GEOMETRY_SERVICE = "GeometryToolsGeometryService"
    GEOMETRY_TOOLS_GEOMETRY_TOOLS = "GeometryToolsGeometryTools"
    GEOMETRY_TOOLS_GEOMETRY_TOOLS_ADMIN = "GeometryToolsGeometryToolsAdmin"


class ArcLayerType(str, Enum):
    """
    ArcGIS layer geometry types
    """

    POINT = "esriGeometryPoint"
    MULTIPOINT = "esriGeometryMultipoint"
    POLYLINE = "esriGeometryPolyline"
    POLYGON = "esriGeometryPolygon"
    RASTER = "esriGeometryRaster"
    UNKNOWN = "esriGeometryUnknown"
    ENVELOPE = "esriGeometryEnvelope"
    EXTENT = "esriGeometryExtent"
    CIRCULAR_ARC = "esriGeometryCircularArc"
    CIRCULAR_ARC_Z = "esriGeometryCircularArcZ"
    CIRCULAR_ARC_M = "esriGeometryCircularArcM"
    CIRCULAR_ARC_Z_M = "esriGeometryCircularArcZM"
    TRIANGLE = "esriGeometryTriangle"
    TRIANGLE_Z = "esriGeometryTriangleZ"
    TRIANGLE_M = "esriGeometryTriangleM"
    TRIANGLE_Z_M = "esriGeometryTriangleZM"
    POLYGON_Z = "esriGeometryPolygonZ"
    POLYGON_M = "esriGeometryPolygonM"
    POLYGON_Z_M = "esriGeometryPolygonZM"
    EXTENT_Z = "esriGeometryExtentZ"
    EXTENT_M = "esriGeometryExtentM"
    EXTENT_Z_M = "esriGeometryExtentZM"


class ArcFieldType(str, Enum):
    """
    ArcGIS field types
    """

    STRING = "esriFieldTypeString"
    SHORT = "esriFieldTypeSmallInteger"
    INTEGER = "esriFieldTypeInteger"
    DOUBLE = "esriFieldTypeDouble"
    FLOAT = "esriFieldTypeSingle"
    DATE = "esriFieldTypeDate"
    BLOB = "esriFieldTypeBlob"
    RASTER = "esriFieldTypeRaster"
    GUID = "esriFieldTypeGUID"
    GLOBALID = "esriFieldTypeGlobalID"
    XML = "esriFieldTypeXML"
    GEOMETRY = "esriFieldTypeGeometry"
    RASTER_DATASET = "esriFieldTypeRasterDataset"
    BLOB_DATASET = "esriFieldTypeBlobDataset"
    DATASET = "esriFieldTypeDataset"
    DATASET_NAME = "esriFieldTypeDatasetName"
    GEOMETRY_DATASET = "esriFieldTypeGeometryDataset"
    OBJECT = "esriFieldTypeOID"
    OBJECT_ID = "esriFieldTypeOID"
    SHORT_DATE = "esriFieldTypeSmallDate"
    SHORT_DATETIME = "esriFieldTypeSmallDateTime"
    SHORT_TIME = "esriFieldTypeSmallTime"
    STRING_DATE = "esriFieldTypeStringDate"
    STRING_DATETIME = "esriFieldTypeStringDateTime"
    STRING_TIME = "esriFieldTypeStringTime"
    STRING_DATETIME_TZ = "esriFieldTypeStringDateTimeTZ"
    STRING_DATETIME_UTC = "esriFieldTypeStringDateTimeUTC"
