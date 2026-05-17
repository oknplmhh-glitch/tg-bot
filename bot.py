from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
group_data = {}

def get_gdata(cid):
    if cid not in group_data:
        group_data[cid] = {
            "rate_ex": 0,
            "rate_fee": 0,
            "total_in": 0,
            "total_out": 0,

            # 隐藏U下发
            "hidden_u": 0,

            "list_in": [],
            "list_out": []
        }
    return group_data[cid]


async def send_bill(chat_id, ctx, data):

    in_text = "\n".join(
        f"{i['time']} {i['num']} {i['name']}"
        for i in data["list_in"]
    )

    out_text = "\n".join(
        f"{o['time']} {o['num']}"
        for o in data["list_out"]
    )

    fee_percent = 100 - data["rate_fee"]

    if data["rate_ex"] <= 0:
        in_usd = 0
        out_usd = 0
        remain_usd = 0

    else:

        in_usd = round(
            (data["total_in"] / data["rate_ex"])
            * (fee_percent / 100),
            3
        )

        out_usd = round(
            (data["total_out"] / data["rate_ex"])
            * (fee_percent / 100),
            3
        )

        # 扣除隐藏U
        remain_usd = round(
            (
                (
                    (data["total_in"] - data["total_out"])
                    / data["rate_ex"]
                )
                * (fee_percent / 100)
            )
            - data["hidden_u"],
            3
        )

    msg = f"""
总入 ({len(data["list_in"])})
{in_text}


总出 ({len(data["list_out"])})
{out_text}

入账汇率：{data["rate_ex"]}
扣除费率：{data["rate_fee"]}%
实收比例：{fee_percent}%

入账总数：{data["total_in"]}
入账合计：{in_usd}U

下发总数：{data["total_out"]}
下发合计：{out_usd}U

合计未回：{remain_usd}USD
"""

    await ctx.bot.send_message(chat_id, msg.strip())


async def main_handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    msg = update.message

    if not msg:
        return

    chat_id = msg.chat.id
    text = msg.text.strip()

    d = get_gdata(chat_id)

    # 设置汇率
    if text.startswith("设置汇率"):

        try:

            num = float(text.replace("设置汇率", ""))

            d["rate_ex"] = num

            await msg.reply_text(
                f"✅ 汇率设置成功，当前汇率：{num}"
            )

        except:

            await msg.reply_text(
                "❌ 格式错误，例如：设置汇率6"
            )

    # 设置费率
    elif text.startswith("设置费率"):

        try:

            num = float(text.replace("设置费率", ""))

            d["rate_fee"] = num

            await msg.reply_text(
                f"✅ 费率设置成功，入账费率：{num}%"
            )

        except:

            await msg.reply_text(
                "❌ 格式错误，例如：设置费率9"
            )

    # 入账
    elif text.startswith("+"):

        try:

            money = float(text[1:])

            # +0 查看账单
            if money == 0:
                await send_bill(chat_id, ctx, d)
                return

            nick = ""

            if msg.reply_to_message:
                nick = msg.reply_to_message.from_user.full_name

            now_time = datetime.now().strftime("%m-%d %H:%M")

            d["list_in"].append({
                "time": now_time,
                "num": money,
                "name": nick
            })

            d["total_in"] += money

            await send_bill(chat_id, ctx, d)

        except:
            pass

    # 下发
    elif text.startswith("下发"):

        try:

            raw = text.replace("下发", "").strip()

            # 带u -> 隐藏扣U
            if raw.lower().endswith("u"):

                money = float(raw[:-1])

                # 不显示
                # 不记录
                # 只扣除未回U
                d["hidden_u"] += money

            # 普通人民币下发
            else:

                money = float(raw)

                now_time = datetime.now().strftime("%m-%d %H:%M")

                d["list_out"].append({
                    "time": now_time,
                    "num": money
                })

                d["total_out"] += money

            await send_bill(chat_id, ctx, d)

        except:
            pass

    # 撤销上一笔入款
    elif text == "撤销入款":

        if d["list_in"]:

            last = d["list_in"].pop()

            d["total_in"] -= last["num"]

            await send_bill(chat_id, ctx, d)

    # 撤销上一笔出款
    elif text == "撤销出款":

        if d["list_out"]:

            last = d["list_out"].pop()

            d["total_out"] -= last["num"]

            await send_bill(chat_id, ctx, d)

    # 清除今日金额
    elif text == "清除今日金额":

        d["total_in"] = 0
        d["total_out"] = 0
        d["hidden_u"] = 0

        d["list_in"].clear()
        d["list_out"].clear()

        await msg.reply_text(
            "✅ 今日所有金额数据已清空"
        )

        await send_bill(chat_id, ctx, d)


if __name__ == "__main__":

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            main_handle
        )
    )

    print("机器人已启动")

    app.run_polling()