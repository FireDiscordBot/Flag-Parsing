class NoDict(dict):
    def __getitem__(self, item):
        return None


class ParamDefault:
    """
    This is the base class for Parameter Defaults.
    Credit to khazhyk (github) for this idea.
    """
    async def default(self, ctx):
        raise NotImplementedError("Must be subclassed.")


class EmptyFlags(ParamDefault):
    async def default(self, ctx):
        return NoDict()
