import inspect
import typing

from discord.ext import commands

from ._default import ParamDefault
from ._converter import FlagParser


def _convert_to_bool(argument):
    lowered = argument.lower()
    if lowered in ('yes', 'y', 'true', 't', '1', 'enable', 'on'):
        return True
    elif lowered in ('no', 'n', 'false', 'f', '0', 'disable', 'off'):
        return False
    else:
        raise commands.BadArgument(lowered + ' is not a recognised boolean option')


class FlagCommand(commands.Command):
    @property
    def signature(self):
        """Returns a POSIX-like signature useful for help command output."""
        if self.usage is not None:
            return self.usage

        params = self.clean_params
        if not params:
            return ''

        result = []
        for name, param in params.items():
            if isinstance(param.annotation, FlagParser):
                fmt = []

                for flag_name, flag_type in param.annotation.flags.items():
                    actual_type = flag_type.__name__ if inspect.isclass(flag_type) else type(flag_type).__name__

                    if actual_type == 'bool':
                        bool_flag = '-{0}' if len(flag_name) == 1 else '--{0}'
                        fmt.append(bool_flag.format(flag_name))
                        continue
                    if len(flag_name) == 1:
                        fmt.append('-{0} {1}'.format(flag_name, actual_type))
                        continue

                    fmt.append('--{0}={1}'.format(flag_name, actual_type))

                sig = ['[{0}]'.format(f) if param.default is not param.empty else '<{0}>'.format(f) for f in fmt]
                result.append(' '.join(sig))
                continue

            greedy = isinstance(param.annotation, commands.converter._Greedy)

            try:
                # noinspection PyTypeChecker
                isdefault = issubclass(param.default, ParamDefault)
            except TypeError:
                # TypeError gets raised because sometimes param.default isn't a class, it's an object.
                isdefault = False

            if param.default is not param.empty and not isdefault:
                # We don't want None or '' to trigger the [name=value] case and instead it should
                # do [name] since [name=None] or [name=] are not exactly useful for the user.
                should_print = param.default if isinstance(param.default, str) else param.default is not None
                if should_print:
                    result.append('[%s=%s]' % (name, param.default) if not greedy else
                                  '[%s=%s]...' % (name, param.default))
                    continue
                else:
                    result.append('[%s]' % name)

            elif param.kind == param.VAR_POSITIONAL:
                result.append('[%s...]' % name)
            elif greedy:
                result.append('[%s]...' % name)
            elif self._is_typing_optional(param.annotation) or isdefault:
                result.append('[%s]' % name)
            else:
                result.append('<%s>' % name)

        return ' '.join(result)

    async def _resolve_default(self, ctx, param):
        try:
            if inspect.isclass(param.default) and issubclass(param.default, ParamDefault):
                instance = param.default()
                return await instance.default(ctx)
            elif isinstance(param.default, ParamDefault):
                return await param.default.default(ctx)
        except commands.CommandError:
            raise
        except Exception as e:
            raise commands.ConversionError(param.default, e) from e
        return None if param.default is param.empty else param.default

    async def _actual_conversion(self, ctx, converter, argument, param):
        if converter is bool:
            return _convert_to_bool(argument)

        try:
            module = converter.__module__
        except AttributeError:
            pass
        else:
            if not isinstance(converter, FlagParser) and \
              module is not None and (module.startswith('discord.') and not module.endswith('converter')):
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

            raise commands.BadArgument('Converting to "{}" failed for parameter "{}".'.format(name, param.name)) from exc

    async def do_conversion(self, ctx, converter, argument, param):
        try:
            origin = converter.__origin__
        except AttributeError:
            pass
        else:
            if origin is typing.Union:
                errors = []
                _NoneType = type(None)
                for conv in converter.__args__:
                    # if we got to this part in the code, then the previous conversions have failed
                    # so we should just undo the view, return the default, and allow parsing to continue
                    # with the other parameters
                    if conv is _NoneType and param.kind != param.VAR_POSITIONAL:
                        ctx.view.undo()
                        return await self._resolve_default(ctx, param)

                    try:
                        value = await self._actual_conversion(ctx, conv, argument, param)
                    except commands.CommandError as exc:
                        errors.append(exc)
                    else:
                        return value

                # if we're  here, then we failed all the converters
                raise commands.BadUnionArgument(param, converter.__args__, errors)

        return await self._actual_conversion(ctx, converter, argument, param)

    async def transform(self, ctx, param):
        required = param.default is param.empty
        converter = self._get_converter(param)
        consume_rest_is_special = param.kind == param.KEYWORD_ONLY and not self.rest_is_raw
        view = ctx.view
        view.skip_ws()

        # The greedy converter is simple -- it keeps going until it fails in which case,
        # it undos the view ready for the next parameter to use instead
        if type(converter) is commands.converter._Greedy:
            if param.kind == param.POSITIONAL_OR_KEYWORD:
                return await self._transform_greedy_pos(ctx, param, required, converter.converter)
            elif param.kind == param.VAR_POSITIONAL:
                return await self._transform_greedy_var_pos(ctx, param, converter.converter)
            else:
                # if we're here, then it's a KEYWORD_ONLY param type
                # since this is mostly useless, we'll helpfully transform Greedy[X]
                # into just X and do the parsing that way.
                converter = converter.converter

        if view.eof:
            if param.kind == param.VAR_POSITIONAL:
                raise RuntimeError()  # break the loop
            if required:
                raise commands.MissingRequiredArgument(param)
            return await self._resolve_default(ctx, param)

        previous = view.index
        if consume_rest_is_special:
            argument = view.read_rest().strip()
        else:
            argument = view.get_quoted_word()
        view.previous = previous

        return await self.do_conversion(ctx, converter, argument, param)
