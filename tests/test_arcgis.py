from lit_data.arcgis import ArcFolder, ArcServer, ArcService
import pytest

# TODO: Implement tests for the ArcGIS API util classes.
SAMPLE_SERVER = "https://sampleserver6.arcgisonline.com/arcgis/rest/services"


@pytest.mark.vcr
def test_server_get_folders():
    server = ArcServer(SAMPLE_SERVER)
    folders = server.folders()
    folder_by_name = server.folders("AGP")

    assert type(folders) == dict
    assert type(folder_by_name) == ArcFolder
    assert len(folders) == 13

    assert folders.get("AGP") is folder_by_name
    assert folder_by_name.name == "AGP"


@pytest.mark.vcr
@pytest.mark.skip(reason="Sample server currently out of date and incompatible")
def test_server_get_services():

    server = ArcServer(SAMPLE_SERVER)
    services = server.services()
    service_by_name = server.services("Census")

    assert type(services) == dict
    assert type(service_by_name) == ArcService

    assert services.get("Census") is service_by_name
    assert service_by_name.name == "Census"
