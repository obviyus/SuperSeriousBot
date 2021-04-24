from typing import TYPE_CHECKING, Dict

import requests

if TYPE_CHECKING:
    import telegram
    import telegram.ext

API_ENDPOINT: str = "https://api.covid19india.org/v4/data.json"


def total() -> str:
    r: Dict[str, Dict] = requests.get(API_ENDPOINT).json()

    text = f"""COVID-19 India Stats: """

    population = r["TT"]["meta"]["population"]
    text += "\n\nTotal Population: {:,}".format(r["TT"]["meta"]["population"])

    cases = r["TT"]["total"]["confirmed"]
    recoveries = r["TT"]["total"]["recovered"]
    tests = r["TT"]["total"]["tested"]
    deceased = r["TT"]["total"]["deceased"]
    vaccinated = r["TT"]["total"]["vaccinated"]

    text += f"\n\n % of total population:"
    text += f"""\nTotal Cases: {"{:,}".format(cases)} ({round(cases / population * 100, 2)}%)"""
    text += f"""\nTotal Tested: {"{:,}".format(tests)} ({round(tests / population * 100, 2)}%)"""
    text += f"""\nTotal Vaccinations: {"{:,}".format(vaccinated)} ({round(vaccinated / population * 100, 2)}%)"""

    text += f"\n\n % of total cases"
    text += f"""\nTotal Recoveries: {"{:,}".format(recoveries)} ({round(recoveries / cases * 100, 2)}%)"""
    text += f"""\nTotal Deaths: {"{:,}".format(deceased)} ({round(deceased / cases * 100, 2)}%)"""

    return text


def statewise(state_name: str) -> str:
    try:
        r = requests.get(API_ENDPOINT).json()
        _ = r[state_name]
    except KeyError:
        return "Invalid state code."

    text = f"COVID-19 Stats for {state_name}:"

    text += "\n\nTotal Cases: {:,}".format(r[state_name]["total"]["confirmed"])
    text += "\nTotal Recoveries: {:,}".format(r[state_name]["total"]["recovered"])
    text += "\nTotal Tested: {:,}".format(r[state_name]["total"]["tested"])
    text += "\nTotal Deceased: {:,}".format(r[state_name]["total"]["deceased"])
    text += "\nTotal Vaccinated: {:,}".format(r[state_name]["total"]["vaccinated"])
    text += "\nTotal Population: {:,}".format(r[state_name]["meta"]["population"])

    text += f"\n\n{state_name} vs. Total:"
    text += f"""\n{round(r[state_name]["meta"]["population"] / r["TT"]["meta"]["population"] * 100, 2)}% of population"""
    text += f"""\n{round(r[state_name]["total"]["confirmed"] / r["TT"]["total"]["confirmed"] * 100, 2)}% of cases"""
    text += f"""\n{round(r[state_name]["total"]["tested"] / r["TT"]["total"]["tested"] * 100, 2)}% of testing"""
    text += f"""\n{round(r[state_name]["total"]["deceased"] / r["TT"]["total"]["deceased"] * 100, 2)}% of deaths"""
    text += f"""\n{round(r[state_name]["total"]["vaccinated"] / r["TT"]["total"]["vaccinated"] * 100, 2)}% of vaccinations"""

    return text


def covid(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get COVID-19 India cases"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    query: str = context.args if context.args else ''

    if not query:
        text = "*Usage:* `/covid {STATE_NAME}`\n" \
               "*Example:* `/covid MH`" \
               "\nTo see total stats use `\covid TT`"
    else:
        if context.args[0] == 'TT':
            text = total()
        else:
            text = statewise(context.args[0])

    message.reply_text(text=text)
