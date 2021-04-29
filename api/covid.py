from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext

import io

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

params = {
    'legend.fontsize': 20,
    'legend.handlelength': 2,
    'font.family': "monospace",
    'figure.figsize': (15, 10),
}
plt.rcParams.update(params)
plt.style.use("dark_background")

state_dict = {
    "AN": "Andaman and Nicobar Islands", "AP": " Andhra Pradesh", "AR": "Arunachal Pradesh", "AS": " Assam",
    "BR": "Bihar", "CH": "Chandigarh", "CT": "Chhattisgarh", "DN": "Dadra and Nagar Haveli",
    "DD": "Daman and Diu", "DL": "Delhi", "GA": "Goa", "GJ": "Gujarat", "HR": "Haryana",
    "HP": " Himachal Pradesh", "JK": "Jammu and Kashmir", "JH": "Jharkand", "KA": "Karnataka", "KL": "Kerala",
    "LA": "Ladakh", "LD": "Lakshadweep", "MP": "Madhya Pradesh", "MH": "Maharashtra", "MN": "Manipur",
    "ML": "Meghalaya", "MZ": "Mizoram", "NL": "Nagaland", "OR": "Odisha", "PY": "Puducherry", "PB": "Punjab",
    "RJ": "Rajasthan", "SK": "Sikkim", "TN": "Tamil Nadu", "TG": "Telangana", "TR": "Tripura",
    "UP": "Uttar Pradesh", "UT": "Uttarakhand", "WB": "West Bengal"
}


def total(buffer: io.BytesIO, days: int) -> None:
    plt.rcParams['axes.prop_cycle'] = plt.cycler(color=['#ea5455', '#1fab89', '#b19cd9'])

    CSV_TIME_SERIES: str = "https://api.covid19india.org/csv/latest/case_time_series.csv"
    df = pd.read_csv(CSV_TIME_SERIES)

    df = df.drop(['Total Confirmed', 'Total Recovered', 'Total Deceased', 'Date'], axis=1, errors='ignore')

    index = pd.date_range(start=df['Date_YMD'][0], end=df['Date_YMD'][len(df) - 1], freq="D")
    index = [pd.to_datetime(date, format='%Y-%m-%d').date() for date in index]
    df.index = index

    if days:
        df = df.tail(days)

    df = df.drop('Date_YMD', axis=1)
    ax = df.plot(y=['Daily Confirmed', 'Daily Recovered', 'Daily Deceased'], kind='line', linewidth=2.0)

    if not days or (days and days > 100):
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%B %Y'))
    plt.gcf().autofmt_xdate()

    plt.xlabel("Month")
    plt.ylabel("Number of Cases")
    plt.title("COVID-19 India")

    plt.savefig(buffer, format='png', pad_inches=0.1, bbox_inches='tight')
    del df


def top_states(buffer: io.BytesIO, days: int) -> None:
    plt.rcParams['axes.prop_cycle'] = plt.cycler(color=["#6886c5", "#f1935c", "#a1cae2", "#cd5d7d", "#838383"])

    CSV_TIME_SERIES: str = "https://api.covid19india.org/csv/latest/state_wise_daily.csv"
    df = pd.read_csv(CSV_TIME_SERIES)
    df = df.drop(['Date', 'TT'], axis=1)

    index = pd.date_range(start=df['Date_YMD'][0], end=df['Date_YMD'][len(df) - 1], freq="D")
    index = [pd.to_datetime(date, format='%Y-%m-%d').date() for date in index]

    confirmed = df.iloc[::3, :]
    confirmed.index = index

    if days:
        confirmed = confirmed.tail(days)
    confirmed = confirmed.dropna().drop(['Date_YMD', 'Status'], axis=1)

    s = confirmed.sum().sort_values(ascending=False, inplace=False)
    confirmed = confirmed[s.index[:5]]

    confirmed: pd.DataFrame = confirmed[confirmed.select_dtypes(include=[np.number]).ge(0).all(1)]

    for column in confirmed.columns.values:
        confirmed.rename(columns={column: state_dict[column]}, inplace=True)

    ax = confirmed.dropna().plot(kind='line', linewidth=2.0)

    if not days or (days and days > 100):
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%B %Y'))

    plt.xlabel("Month")
    plt.ylabel("Number of Cases")

    plt.title("COVID-19 India - Top 5 Most Affected States")
    plt.gcf().autofmt_xdate()

    plt.savefig(buffer, format='png', bbox_inches='tight', pad_inches=0.1)
    del [df, confirmed, s]


def statewise(buffer: io.BytesIO, state_name: str, days) -> None:
    plt.rcParams['axes.prop_cycle'] = plt.cycler(color=['#ea5455', '#1fab89', '#b19cd9'])
    if state_name not in state_dict:
        return

    CSV_TIME_SERIES: str = "https://api.covid19india.org/csv/latest/state_wise_daily.csv"
    df = pd.read_csv(CSV_TIME_SERIES)
    df = df[['Date_YMD', 'Status', state_name]]

    index = pd.date_range(start=df['Date_YMD'][0], end=df['Date_YMD'][len(df) - 1], freq="D")
    index = [pd.to_datetime(date, format='%Y-%m-%d').date() for date in index]

    confirmed = df.iloc[::3, :]
    recovered = df.iloc[1::3, :]
    deceased = df.iloc[2::3, :]

    confirmed.index = index
    confirmed = confirmed.dropna().drop(['Date_YMD', 'Status'], axis=1)

    recovered.index = index
    recovered = recovered.dropna().drop(['Date_YMD', 'Status'], axis=1)

    deceased.index = index
    deceased = deceased.dropna().drop(['Date_YMD', 'Status'], axis=1)

    state = confirmed[[state_name]]

    state['Confirmed'] = confirmed[[state_name]]
    state['Recovered'] = recovered[[state_name]]
    state['Deceased'] = deceased[[state_name]]

    if days:
        state = state.tail(days)

    state = state.drop([state_name], axis=1)
    state = state[state.select_dtypes(include=[np.number]).ge(0).all(1)]

    ax = state.dropna().plot(kind='line', linewidth=2.0)

    if not days or (days and days > 100):
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%B %Y'))
    plt.gcf().autofmt_xdate()

    plt.xlabel("Month")
    plt.ylabel("Number of Cases")
    plt.title(f"COVID-19 India - {state_dict[state_name]}")

    plt.savefig(buffer, format='png', bbox_inches='tight', pad_inches=0.1)
    del [df, state, confirmed, deceased, recovered]


def covid(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get COVID-19 India cases"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    query: str = context.args if context.args else ''

    if not query:
        text = "*Usage:* `/covid {STATE_NAME} {OPTIONAL: LAST N DAYS}`" \
               "*\nExample:* `/covid MH 100`" \
               "\nTo see total country stats use `\covid TT`"
        message.reply_text(text)
    else:
        days = int(context.args[1]) if len(context.args) > 1 else None
        context.args[0] = context.args[0].upper()
        buf = io.BytesIO()

        if context.args[0] == 'TT':
            total(buf, days)
        elif context.args[0] == 'TOP':
            top_states(buf, days)
        elif context.args[0] in state_dict:
            statewise(buf, context.args[0], days)
        else:
            message.reply_text(text="Invalid code.")
            return

        buf.seek(0)
        message.reply_photo(photo=buf)

        buf.close()
        plt.close("all")
