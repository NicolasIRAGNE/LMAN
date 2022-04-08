################################################################################
# File: lman.py
# Created Date: Fri Apr 08 2022
# Author: jamky from prismatic
# -----
# i wrote this to save people from naeth
# this script parses raw csv results from raidbots.com and attempts to
# fill the lootsheet™️
# -----
################################################################################

from tkinter import commondialog, simpledialog
from urllib import request
import pyperclip
from tkinter import *
from tkinter import messagebox

encounter_ids = {2458: 'Guardian',
                 2465: 'Skolex',
                 2470: 'Xy\'Mox',
                 2459: 'Dausegne',
                 2460: 'Pantheon',
                 2461: 'Lihuvim',
                 2463: 'Halondrius',
                 2469: 'Anduin',
                 2457: 'Dreadlords',
                 2467: 'Rygelon',
                 2464: 'Jailer',
                 -24: 'Trash'}


# Order in the lootsheet:
#              GUARDIAN	DAUSEGNE PANTHEON LIHUVIM SKOLEX XY'MOX HALONDRUS ANDUIN DREADLORDS RYGELON JAILER
ordered_ids = [2458,    2459,    2460,    2461,   2465,  2470,  2463,     2469,  2457,      2467,   2464]


def process_results(results_link_raw):
    '''
    Turns the response from raidbots into human readable data
    An example response looks like this:
    "
    name,dps_mean,dps_min,dps_max,dps_std_dev,dps_mean_std_dev
    Yoksha,12883.549125961325,10572.857204708445,15813.353484516962,619.2796712030228,3.2830980411435555
    1195/2467/raid-mythic/188839/6230/chest/,13101.687508079911,10590.857448969044,15881.246593615091,631.9862020730385,3.34094420154005
    <additional rows for every eligible item>
    "
    Here is a breakdown of the data:
    * First line is the header that contains the column names
    * Second line is the Player's current stats
    * Any following lines are a potential item with the following format:
        * <raid_id>/<encounter_id>/<raid_type>/<item_id>/<unknown>/<item_slot>,<dps_mean>,<dps_min>,<dps_max>,<dps_std_dev>,<dps_mean_std_dev>

    This function will return a dictionary associating an encounter_id with a letter that indicates how big of an upgrade potential loot is:
    * S: Small (< 1% upgrade potential)
    * B: Big (> 1% upgrade potential)
    * N: No upgrade potential

    :param results_link: The link to raidbots.com. Can be either in the form of https://www.raidbots.com/simbot/report/<id> or https://www.raidbots.com/reports/<id>/data.csv. In case of the latter, the link will be converted to the former.
    '''
    # Get the data from raidbots
    if not results_link_raw.endswith('.csv'):
        id = results_link_raw.split('/')[-1]
        results_link = 'https://www.raidbots.com/reports/' + id + '/data.csv'
    else:
        results_link = results_link_raw

    req = request.Request(
        results_link,
        data=None,
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
        }
    )
    response = request.urlopen(req)
    response_data = response.read().decode('utf-8')
    upgrades = {}
    # get the header line
    header = response_data.split('\n')[0]
    # get the player's stats
    player_stats = response_data.split('\n')[1]
    # get the player's dps
    player_dps = float(player_stats.split(',')[1])
    # now compare the dps of each item to the player's dps
    for line in response_data.split('\n')[2:]:
        if line == '':
            continue
        # get encounter_id
        encounter_id = int(line.split(',')[0].split('/')[1])
        # get dps
        dps = float(line.split(',')[1])
        # get upgrade potential
        upgrade_potential = dps - player_dps
        if encounter_id not in upgrades or upgrade_potential > upgrades[encounter_id]:
            upgrades[encounter_id] = upgrade_potential

    output = ""
    # sort upgrades according to ordered_ids
    # print all upgrades
    for encounter_id in ordered_ids:
        if encounter_id == -24:
            continue
        upgrade_potential = upgrades[encounter_id]
        upgrade_ratio = upgrade_potential / player_dps
        if upgrade_ratio < 0.01 and upgrade_ratio > 0:
            output += 'S'
        elif upgrade_ratio > 0.01:
            output += 'B'
        else:
            output += ''
        output += u'\u0009'
    output += results_link_raw
    print('GUARDIAN DAUSEGNE PANTHEON LIHUVIM SKOLEX XY\'MOX HALONDRUS ANDUIN DREADLORDS RYGELON JAILER')
    print(output)
    pyperclip.copy(output)
    return output


def button_wrapper(results_link, status_text):
    try:
        process_results(results_link)
        status_text.set('Copied to clipboard')
    except Exception as e:
        status_text.set('There was an error: ' + str(e))


if __name__ == '__main__':
    # window prompt for link
    x = simpledialog.askstring("Input", "Enter raidbots.com link:")
    status = ""
    try:
        process_results(x)
        status = "Copied to clipboard"
        msgbox = messagebox.showinfo("Results", status)
    except Exception as e:
        status = "There was an error: " + str(e)
        msgbox = messagebox.showerror("Results", status)

    pass
