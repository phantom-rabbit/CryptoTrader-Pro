from live import live
import click


@live.command()
@click.pass_context
@click.option('--boll_period', type=int, default=60, required=True, help="布林带的周期长度")
@click.option('--boll_dev', type=float, default=4.0, required=True, help="布林带的标准差倍数")
@click.option('--rsi_period', type=int, default=80, required=True, help="RSI周期")
@click.option('--rsi_buy_signal', type=float, default=41.5, required=True, help="买入信号")
@click.option('--stop_loss', type=float, default=0.3, required=True, help="止损百分比")
@click.option('--rsi_downward_period', type=int, default=8, required=True, help="RSI联系下降周期")
def RSIReversal(ctx, boll_period, boll_dev, rsi_period, rsi_buy_signal, stop_loss, rsi_downward_period):
    config = ctx.obj
    print(config)