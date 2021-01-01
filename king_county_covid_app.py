#! /usr/bin/env python3
import kaggle
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from matplotlib import pyplot as plt
from matplotlib import dates
from matplotlib import patches
from kaggle.api.kaggle_api_extended import KaggleApi
import tweepy
from twitter_key import consumer_key, consumer_key_secret, access_token, access_token_secret

api = KaggleApi()
api.authenticate()


def update_data():
    # update local file with kaggle dataset
    # Dataset: https://www.kaggle.com/headsortails/covid19-us-county-jhu-data-demographics
    folder = os.getcwd()
    kaggle.api.dataset_download_files('headsortails/covid19-us-county-jhu-data-demographics', path=folder, unzip=True)
    df = pd.read_csv(folder+'\\covid_us_county.csv', parse_dates=['date'])

    return df


def filter_wa_kc(df):
    # Creates dataframe filtered for Washington State, King County
    a = df[(df['state_code'] == 'WA') & (df['county'] == 'King')]
    b = a[['date', 'cases', 'deaths']].copy()

    b['1 Day New Cases'] = b['cases'].diff()
    b['7 Day New Cases'] = b['1 Day New Cases'].rolling(window=7).sum()
    b['Weekly Rate'] = [(x / king_county_pop) * 100000 for x in b['7 Day New Cases']]
    b.set_index('date', inplace=True)

    return b


def filter_wa_state(df):
    # Creates dataframe filter for Washington State
    a = df[(df['state_code'] == 'WA')].copy()
    b = a[['date', 'cases', 'deaths']].copy()
    c = b.groupby(['date'], as_index=True)['cases'].sum().groupby(level=0).cumsum().reset_index()
    d = b.groupby(['date'], as_index=True)['deaths'].sum().groupby(level=0).cumsum().reset_index()
    d.set_index('date', inplace=True)

    c['1 Day New Cases'] = c['cases'].diff()
    c['7 Day New Cases'] = c['1 Day New Cases'].rolling(window=7).sum()
    c['Weekly Rate'] = [(x / wa_state_pop) * 100000 for x in c['7 Day New Cases']]
    c.set_index('date', inplace=True)

    merge = pd.merge(c, d, how='inner', left_index=True, right_index=True)

    return merge


def plot_data(ax, df, label, color):
    # creates 3 month window for plot
    df = df.loc[str(window):str(yesterday)]

    # plots weekly rate per 100k line
    s_d = ax.plot_date(df.index, df['Weekly Rate'], color=color, linestyle='-', marker=None,
                       label=label, linewidth=2)


def style_plot(fig, ax):
    ax.set_title('COVID-19 Rates in King County, Washington State')
    ax.set_ylabel('Weekly Cases per 100,000 Population')
    ax.grid(axis='y')

    ax.set_xlim([window, datetime.today().date()])
    ax.set_ylim(bottom=0)

    # Sets month as major ticks and weeks as minor ticks
    ax.xaxis.set_major_locator(dates.MonthLocator())
    ax.xaxis.set_minor_locator(dates.DayLocator(bymonthday=(8, 15, 22)))

    # Add today's date as final tick on x-axis
    today = datetime.today().date()
    if today - today.replace(day=1) > timedelta(days=15):
        ax.set_xticks(np.append(ax.get_xticks(), dates.date2num(datetime.today().date())))

    # Format x-axis dates as 'day month abbreviation'
    ax.xaxis.set_major_formatter(dates.DateFormatter('%d %b'))

    # Visualization of Nov. 16 - Jan 4 Washington State COVID19 restrictions
    start, end = datetime(2020, 11, 16), datetime(2021, 1, 4)
    lockdown_len = (end - start).days
    restrictions = patches.Rectangle((dates.date2num(start), 0), lockdown_len, ax.get_ylim()[1], fill=True,
                                     color='#cfe1ff', label='WA State Restrictions')
    ax.add_patch(restrictions)

    ax.legend(loc=2)
    fig.savefig('graphic.png', bbox_inches='tight', dpi='figure')
    plt.show()


def write_tweet(dataframe, region):
    # appends plus/minus symbol to str
    sign = lambda i: ("+" if i >= 0 else "") + str(i)

    yesterday_str_1 = yesterday.strftime("%Y-%m-%d")
    yesterday_str_2 = yesterday.strftime("%d %b")
    prev_day_str = prev_day.strftime("%Y-%m-%d")

    cases_daily = int(dataframe.loc[yesterday_str_1]['1 Day New Cases'])
    cases_delta = int(cases_daily - int(dataframe.loc[prev_day_str]['1 Day New Cases']))
    deaths_delta = int(dataframe.loc[yesterday_str_1]['deaths']) - int(dataframe.loc[prev_day_str]['deaths'])
    deaths_cum = int(dataframe.loc[yesterday_str_1]['deaths'])

    tweet_text = (
        f'{region}, {yesterday_str_2}:\n'
        f'Cases Reported: {cases_daily:,} ({sign(cases_delta)} from {prev_day.strftime("%d %b")})\n'
        f'Total Deaths:   {deaths_cum:,} ({sign(deaths_delta)} from {prev_day.strftime("%d %b")})\n'
        f'\n'
    )

    return tweet_text


def send_tweet(text):
    auth = tweepy.OAuthHandler(consumer_key, consumer_key_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)

    try:
        api.verify_credentials()
        print("Authentication OK")
    except:
        print("Error during authentication")

    image = api.media_upload('graphic.png')

    api.update_status(text, media_ids=[image.media_id, ])
    print('Tweet successfully sent')

# Statistics acquired from:
# https://worldpopulationreview.com/us-counties/states/wa
# https://www.kingcounty.gov/independent/forecasting/King%20County%20Economic%20Indicators/Demographics.aspx
# https://www.ofm.wa.gov/washington-data-research/statewide-data/washington-trends/population-changes/total-population-and-percent-change
king_county_pop = 2277200  # 2260800
wa_state_pop = 7656200


if __name__ == '__main__':
    yesterday = datetime.today().date() - timedelta(days=1)
    prev_day = yesterday - timedelta(days=1)
    window = yesterday + relativedelta(months=-3)

    figure, axes = plt.subplots(figsize=(6, 5))
    king_county_df = filter_wa_kc(update_data())
    wa_state_df = filter_wa_state(update_data())
    plot_data(axes, wa_state_df, 'Washington State', '#4d00ff')
    plot_data(axes, king_county_df, 'King County', '#ffa600')

    style_plot(figure, axes)

    tweet = (write_tweet(king_county_df, 'King County') +
             write_tweet(wa_state_df, 'Washington State') +
             f'Data from John Hopkins University.')

    send_tweet(tweet)
