# Flag Parsing
A util for discord.py bots that allow passing flags into commands.

To install, run the following command:
```
pip install discord-flags
```

Basic example usage:

```python
import discord
from discord.ext import flags, commands

bot = commands.Bot("!")

# Invocation: !flags --count=5 --string=hello world --user=Xua --thing

@bot.command(cls=flags.FlagCommand)
async def flags(ctx, *, flag: flags.FlagParser(
    count=int,
    string=str,
    user=discord.User,
    thing=bool
) = flags.EmptyFlags):
    c = flag['count']
    s = flag['string']
    u = flag['user']
    t = flag['thing']
    # Ignore any error about EmptyFlags not implementing __getitem__
    
    await ctx.send(f"--count: {type(c).__name__} {c}\n"
                   f"--string: {type(s).__name__} {s}\n"
                   f"--user: {type(u).__name__} {u}\n"
                   f"--thing: {type(t).__name__}: {t}")
    # Will output:
    # --count: int 5
    # --string: str hello world
    # --user: User Xua#4427       
    # --thing: True
```

Quick docs:

#### flags.EmptyFlags

This will return a dict which every key will always return None.
This is for when no flags are specified.
If flags are specified, any omitted flags will default to None.

#### flags.FlagParser

The converter for the flags. You must pass an instance as a type hint, 
and it must have at least 1 valid flag.

They must be passed as `name=type`.

`user=discord.User` will attempted to convert `--user=Xua` into a user object.
This will raise an error if it fails.

#### flags.FlagCommand
If you wish to use flags.FlagParser, your command must be a subclass of this command.
This is to ensure that the default arguments are properly converted.

Credit to [khazhyk](https://github.com/Khazhyk) for this idea.


#### flags.ParamDefault
Again, if your command is a subclass of flags.FlagCommand, you can use custom Default arguments
with your command.

Example usage here shows the argument `user` defaulting to the command author, without
the use of `user = None; user = user or ctx.author`

```python
from discord.ext import flags
import discord


class Author(flags.ParamDefault):
    async def default(self, ctx):
        return ctx.author


@bot.command(cls=flags.FlagCommand)
async def me(ctx, user: discord.User = Author):
    await ctx.send(user.mention)
    # will mention you if you do not supply an argument.
```

Credits:
> khazhyk for creating the original pull request for the default function
([link](https://github.com/Rapptz/discord.py/pull/1849))

> Rapptz for creating the discord.py library.