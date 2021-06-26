#! /usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from matplotlib import pyplot as plt
from matplotlib import dates
from matplotlib import patches
import tweepy
from twitter_key import consumer_key, consumer_key_secret, access_token, access_token_secret


# Statistics acquired from:
# https://worldpopulationreview.com/us-counties/states/wa
# https://www.kingcounty.gov/independent/forecasting/King%20County%20Economic%20Indicators/Demographics.aspx
# https://www.ofm.wa.gov/washington-data-research/statewide-data/washington-trends/population-changes/total-population-and-percent-change
king_county_pop = 2277200  # 2260800
wa_state_pop = 7656200
URL_cases = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_US.csv'
URL_deaths = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_deaths_US.csv'


def build_df():
    # Build dataframes from JHU csvs
    df_cases = pd.read_csv(URL_cases, index_col=0)
    df_deaths = pd.read_csv(URL_deaths, index_col=0)

    # .melt() converts dataframe from wide to long format.
    # gets cumulative number of cases from csv
    df_deaths_slim = df_deaths.melt(
        id_vars=df_deaths.columns[0],
        value_vars=df_deaths.columns[11:],
        value_name='reported_deaths'
    )
    # Converts df_cases to long format. Removes non-essential columns.
    df = df_cases.melt(
        id_vars=df_cases.columns[4:6],
        value_vars=df_cases.columns[11:],
        value_name='reported_cases',
        var_name='date'
    )

    # dataframe formatting
    df.columns = ['county', 'state', 'date', 'reported_cases']
    df['reported_deaths'] = df_deaths_slim['reported_deaths']
    df['date'] = pd.to_datetime(df['date'])

    return df


def filter_wa_kc(df):
    # Creates dataframe filtered for Washington State, King County
    a = df[(df['state'] == 'Washington') & (df['county'] == 'King')].copy()

    a['1 Day New Cases'] = a['reported_cases'].diff()
    a['7 Day New Cases'] = a['1 Day New Cases'].rolling(window=7).sum()
    a['Weekly Rate'] = [(x / king_county_pop) * 100000 for x in a['7 Day New Cases']]
    a.set_index('date', inplace=True)

    return a


def filter_wa_state(df):
    # Creates dataframe filtered for Washington State
    a = df[(df['state'] == 'Washington')].copy()
    # Data is divided by state and county, values need to be combined.
    b = a.groupby(['date'], as_index=True)['reported_cases'].sum().groupby(level=0).cumsum().reset_index()
    c = a.groupby(['date'], as_index=True)['reported_deaths'].sum().groupby(level=0).cumsum().reset_index()
    c.set_index('date', inplace=True)

    b['1 Day New Cases'] = b['reported_cases'].diff()
    b['7 Day New Cases'] = b['1 Day New Cases'].rolling(window=7).sum()
    b['Weekly Rate'] = [(x / wa_state_pop) * 100000 for x in b['7 Day New Cases']]
    b.set_index('date', inplace=True)

    merge = pd.merge(b, c, how='inner', left_index=True, right_index=True)

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

    ''' DEFUNCT - Visualization of Nov. 16 - Jan 4 Washington State COVID19 restrictions 
    start, end = datetime(2020, 11, 16), datetime(2021, 1, 4)
    lockdown_len = (end - start).days
    restrictions = patches.Rectangle((dates.date2num(start), 0), lockdown_len, ax.get_ylim()[1], fill=True,
                                     color='#cfe1ff')
    ax.add_patch(restrcitions)
    '''

    ''' Washington State enters Phase 3 of "Healthy Washington - Road to Recovery" Plan
    phase3_start = datetime(2021, 3, 22)
    phase3 = patches.Rectangle((dates.date2num(phase3_start), 0), 1, ax.get_ylim()[1], fill=True,
                               color='#b7d660', label='WA Phase 3 Begins')
    ax.add_patch(phase3)
    '''

    # WA State DOH approves Vaccination for ages 12 and older
    twelveup_start = datetime(2021, 5, 12)
    twelveup = patches.Rectangle((dates.date2num(twelveup_start), 0), 1, ax.get_ylim()[1], fill=True,
                                 color='#00ff7b', label='Vaccine Eligibility(12+)')
    ax.add_patch(twelveup)

    # loc=1 - upper-right, loc=2 - upper-left
    ax.legend(loc=2)
    fig.savefig('graphic.png', bbox_inches='tight', dpi='figure')
    plt.show()


def write_tweet(dataframe, region):
    # appends plus/minus symbol to str
    sign = lambda i: ("+" if i >= 0 else "") + str(i)

    yesterday_str = yesterday.strftime("%Y-%m-%d")
    prev_day_str = prev_day.strftime("%Y-%m-%d")

    cases_daily = int(dataframe.loc[yesterday_str]['1 Day New Cases'])
    cases_delta = int(cases_daily - int(dataframe.loc[prev_day_str]['1 Day New Cases']))
    deaths_delta = int(dataframe.loc[yesterday_str]['reported_deaths']) - int(dataframe.loc[prev_day_str]['reported_deaths'])
    deaths_cum = int(dataframe.loc[yesterday_str]['reported_deaths'])

    tweet_text = (
        f'{region}, {yesterday.strftime("%d %b")}:\n'
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


if __name__ == '__main__':
    # written as - timedelta(days=2), as PythonAnywhere is hosted on UTC time
    yesterday = datetime.today().date() - timedelta(days=1)
    prev_day = yesterday - timedelta(days=1)
    window = yesterday + relativedelta(months=-3)

    wa_kc_df = filter_wa_kc(build_df())
    wa_state_df = filter_wa_state(build_df())

    figure, axes = plt.subplots(figsize=(6, 5))
    plot_data(axes, wa_kc_df, 'King County', '#ffa600')
    plot_data(axes, wa_state_df, 'Washington State', '#4d00ff')
    style_plot(figure, axes)

    tweet = (write_tweet(wa_kc_df, 'King County') +
             write_tweet(wa_state_df, 'Washington State') +
             f'Data from John Hopkins University.')

    send_tweet(tweet)
