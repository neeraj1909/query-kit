class SearchError(Exception):
    pass


class SearchNetworkError(SearchError):
    pass


class ProviderParseError(SearchError):
    pass


class UnknownProviderError(SearchError):
    pass


class ProviderSearchError(SearchError):
    def __init__(
        self, provider_id: str, message: str, *, network_failure: bool = False
    ) -> None:
        self.provider_id = provider_id
        self.network_failure = network_failure
        super().__init__(message)
