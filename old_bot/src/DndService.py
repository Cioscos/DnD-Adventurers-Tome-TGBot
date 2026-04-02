import logging
from typing import Dict, List

import aiohttp

from model.APIResource import APIResource

logger = logging.getLogger(__name__)


class DndService:
    DOMAIN = "https://www.dnd5eapi.co"
    API = "https://www.dnd5eapi.co/api"

    def __init__(self):
        """
        Initialize the DndService with the base API URL, payload, and headers.
        """
        self.__api = self.DOMAIN
        self.__payload = {}
        self.__headers = {
            'Accept': 'application/json'
        }
        self.__session = None

    async def __aenter__(self):
        """
        Async context manager entry. Initialize the aiohttp session.
        """
        self.__session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """
        Async context manager exit. Close the aiohttp session.
        """
        await self.__session.close()

    async def __do_get(self, url: str) -> Dict:
        """
        Fetch data from a specific API URL.

        Args:
            url (str): The API URL to fetch data from.

        Returns:
            dict: The JSON response from the API.
        """
        async with self.__session.get(url, headers=self.__headers) as response:
            response.raise_for_status()
            response = await response.json()
            return response

    async def get_all_resources(self) -> Dict:
        """
        Fetch all resource URLs.

        Returns:
            dict: The JSON response from the API.
        """
        url = f"{self.__api}/api"
        return await self.__do_get(url)

    async def get_available_resources(self, endpoint: str) -> List[APIResource]:
        """
        Get list of all available resources for an endpoint.

        Args:
            endpoint (str): An endpoint name.

        Returns:
            dict: The JSON response from the API.
        """
        url = f"{self.__api}/api/{endpoint}"
        data = await self.__do_get(url)

        available_resources = []
        for resource in data['results']:
            dnd_resource = APIResource(**resource)
            available_resources.append(dnd_resource)

        return available_resources

    async def get_resource_detail(self, path: str) -> Dict:
        """
        Get resource detail.

        Args:
            path (str): Path to the resource detail.

        Returns:
            dict: The JSON response from the API.
        """
        url = f"{self.__api}/api/{path}"
        return await self.__do_get(url)

    async def get_ability_score(self, ability: str) -> Dict:
        """
        Fetch data from a specific API ability score.

        Args:
            ability (str): Ability score to fetch. Possible values: [cha, con, dex, int, str, wis]

        Returns:
            dict: The JSON response from the API.

        Raises:
            ValueError: If the ability is not one of the allowed values.
        """
        if ability not in ["cha", "con", "dex", "int", "str", "wis"]:
            raise ValueError("Ability must be either cha, con, dex, int, str, wis")
        url = f"{self.__api}/api/ability-scores/{ability}"
        return await self.__do_get(url)

    async def get_ability_scores(self) -> Dict:
        """
        Fetch ability scores.
        """
        url = f"{self.__api}/api/ability-scores"
        return await self.__do_get(url)

    async def get_resource_by_class_resource(self, endpoint: str) -> Dict:
        """
        Fetch resource by an endpoint provided from another resource
        :param endpoint: Resource string
        """
        url = f"{self.__api}{endpoint}"
        return await self.__do_get(url)

    async def get_spells_by_class_index(self, class_index: str) -> Dict:
        url = f"{self.__api}/api/classes/{class_index}/spells"
        return await self.__do_get(url)

    async def get_class_levels_by_class_index(self, class_index: str, level: str) -> Dict:
        url = f"{self.__api}/api/classes/{class_index}/levels/{level}"
        return await self.__do_get(url)
