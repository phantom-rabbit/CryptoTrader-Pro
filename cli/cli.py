from cli import live
import click

@click.group()
def cli():
    pass

cli.add_command(live, "live")