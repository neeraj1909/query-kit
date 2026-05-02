class SearchError(Exception):
    pass


class UnknownProviderError(SearchError):
    pass


class ProviderSearchError(SearchError):
    def __init__(self, provider_id: str, message: str) -> None:
        self.provider_id = provider_id
        super().__init__(message)
