from discord.ext.commands import UserInputError


class FlagParsingError(UserInputError):
    def __init__(self, message):
        super().__init__(message)
