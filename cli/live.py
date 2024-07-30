import click
import toml

@click.group()
@click.pass_context
@click.option('--config', "-c", "config", type=click.File('r'), required=True, help='Path to the configuration file.')
def live(ctx, config):
    """实盘交易"""
    ctx.obj = toml.load(config)
