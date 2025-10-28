# integration/services/dahua_service.py
from cctv.api.dahua_api import DahuaAPI
from cctv.api.hikvision_api import HikvisionAPI

# Initialize CCGV instances
dahua_service = DahuaAPI()
hikvision_service = HikvisionAPI()


def get_dahua_client():
    """Return the shared Dahua API client instance."""
    return dahua_service

def get_hikvision_client():
    """Return the shared Hikvision API client instance."""
    return hikvision_service
