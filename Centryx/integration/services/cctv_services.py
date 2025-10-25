# integration/services/dahua_service.py
from cctv.api.dahua_api import DahuaAPI

# Initialize CCGV instances
dahua_service = DahuaAPI()


def get_dahua_client():
    """Return the shared Dahua API client instance."""
    return dahua_service
