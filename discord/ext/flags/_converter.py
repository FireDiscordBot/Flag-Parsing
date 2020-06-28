import inspect
import re

from discord.ext import commands

from ._error import FlagParsingError


FLAG_RE = re.compile(r"(?:--(?:([a-zA-Z_]+)(?:(?:=| )([^\n\-]+))?)|-(?:([a-zA-Z])\s+([^\n\-]+)))")


def _convert_to_bool(argument):
    lowered = argument.lower()
    if lowered in ('yes', 'y', 'true', 't', '1', 'enable', 'on'):
        return True
    elif lowered in ('no', 'n', 'false', 'f', '0', 'disable', 'off'):
        return False
    else:
        raise commands.BadArgument(lowered + ' is not a recognised boolean option')


async def _actual_conversion(ctx, converter, argument):
    if converter is bool:
        return _convert_to_bool(argument)

    try:
        module = converter.__module__
    except AttributeError:
        pass
    else:
        if module is not None and (module.startswith('discord.') and not module.endswith('converter')):
            converter = getattr(commands, converter.__name__ + 'Converter')

    try:
        if inspect.isclass(converter):
            if issubclass(converter, commands.Converter):
                instance = converter()
                ret = await instance.convert(ctx, argument)
                return ret
            else:
                method = getattr(converter, 'convert', None)
                if method is not None and inspect.ismethod(method):
                    ret = await method(ctx, argument)
                    return ret
        elif isinstance(converter, commands.Converter):
            ret = await converter.convert(ctx, argument)
            return ret
    except commands.CommandError:
        raise
    except Exception as exc:
        raise commands.ConversionError(converter, exc) from exc

    try:
        return converter(argument)
    except commands.CommandError:
        raise
    except Exception as exc:
        try:
            name = converter.__name__
        except AttributeError:
            name = converter.__class__.__name__

        ctx.bot.logger.warn(f'Converting to {name} failed.', exc_info=exc)
        raise commands.BadArgument('Converting to "{}" failed.'.format(name)) from exc


class FlagParser(commands.Converter):
    def __init__(self, **expected_flags):
        """:param expected_flags: should be a Dict[Str[FlagName], Type[int, str, ...]]"""
        self.flags = expected_flags

    async def convert(self, ctx, argument):
        """Returns a Dict[FlagName, FlagValue]"""
        _ret = dict()
        flags = self.flags.copy()
        for flag, conv in flags.copy().items():
            if isinstance(conv, list):
                _ret[flag] = []
                flags[flag] = flags[flag][0]
        for fg1, fv1, fg2, fv2 in FLAG_RE.findall(argument):
            flagname = fg1 or fg2
            flagvalue = fv1 or fv2
            if not flagname:
                raise FlagParsingError(argument)
            if not flagvalue:
                flagvalue = "true"
            try:
                conv = flags[flagname]
            except KeyError:
                raise FlagParsingError("Unknown flag \"{}\".".format(flagname))
            flagvalue = await _actual_conversion(ctx, conv, flagvalue.strip())
            if flagname in _ret and isinstance(_ret[flagname], list):
                _ret[flagname].append(flagvalue)
            else:
                _ret[flagname] = flagvalue
        for flag in flags:
            if flag not in _ret:
                _ret[flag] = None
        del flags
        return _ret
