from lit_data.arcgis import ArcFolder, ArcServer, ArcService, ArcServiceType, ArcTable
import pytest

# TODO: Implement tests for the ArcGIS API util classes.


@pytest.fixture(scope="function")  # https://github.com/kiwicom/pytest-recording/issues/76
@pytest.mark.vcr
def server():
    return ArcServer("https://sampleserver6.arcgisonline.com/arcgis/rest/services")


@pytest.mark.vcr
def test_server_folders(server):
    folders = server.folders()
    folder_by_name = server.folders("AGP")

    assert type(folders) == list
    assert type(folder_by_name) == ArcFolder
    assert len(folders) == 13

    assert folders[0] is folder_by_name
    assert folder_by_name.name == "AGP"


@pytest.mark.vcr
def test_server_services(server):
    services = server.services()
    service_by_name = server.services("Military")

    assert len(services) == 60
    assert services[18] is service_by_name
    assert type(service_by_name) is ArcService


@pytest.mark.vcr
def test_service_tables(server):
    service = server.services("ServiceRequest", ArcServiceType.FEATURE_SERVER)
    tables = service.tables()
    print(service._tables)
    table_by_name = service.tables(1)

    assert len(tables) == 1
    assert tables[1] is table_by_name
    assert type(table_by_name) is ArcTable


@pytest.mark.vcr
@pytest.mark.xfail(raises=NotImplementedError, reason="Only FeatureServer currently implemented")
def test_map_service(server):
    map_service = server.services("Military", ArcServiceType.MAP_SERVER)

    assert map_service.service_type == ArcServiceType.MAP_SERVER
    map_service.layers()
