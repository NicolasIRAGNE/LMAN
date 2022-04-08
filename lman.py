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
from tkinter import ttk
import json
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = '1PhDyVmN-SmU7LFsrywR2LKZ8MU2NBY5evXmQujgG5Lo'
SAMPLE_RANGE_NAME = 'Mythic Loot!C28:M28'
USER_RANGE = 'Mythic Loot!C{}:M{}'
USER_RANGE_FORMATTED = ""
NAME_COLUMN = 1
STARTING_COLUMN = 2
NAMES_RANGE = 'Mythic Loot!B8:B'


class Item:
    """This class represents an item from an encounter.

    Constructor arguments:
        :param str line: The line from the csv file. Should be in the format ``<raid_id>/<encounter_id>/<raid_type>/<item_id>/<unknown>/<item_slot>,<dps_mean>,<dps_min>,<dps_max>,<dps_std_dev>,<dps_mean_std_dev>``

    Attributes:
        :ivar int raid_id: The raid id.
        :ivar int encounter_id: The encounter id.
        :ivar str raid_type: The raid type.
        :ivar int item_id: The item id.
        :ivar int item_slot: The item slot.
        :ivar float dps_mean: The mean dps.
        :ivar float dps_min: The minimum dps.
        :ivar float dps_max: The maximum dps.
        :ivar float dps_std_dev: The standard deviation of the dps.
        :ivar float dps_mean_std_dev: The standard deviation of the mean dps.
    """

    def __init__(self, line):
        self.raid_id = int(line.split('/')[0])
        self.encounter_id = int(line.split('/')[1])
        self.raid_type = line.split('/')[2]
        self.item_id = int(line.split('/')[3])
        self.item_slot = str(line.split('/')[5])
        self.dps_mean = float(line.split(',')[1])
        self.dps_min = float(line.split(',')[2])
        self.dps_max = float(line.split(',')[3])
        self.dps_std_dev = float(line.split(',')[4])
        self.dps_mean_std_dev = float(line.split(',')[5])


class LootCell:
    """This class represents a cell in the loot sheet.

    Atttriutes:
        :ivar list items: A list of items in the cell.
        :ivar str upgrade_level: How big of an upgrade the cell is. Can be either ``B`` for big upgrade, ``S`` for small upgrade, or empty for no upgrade.
        :ivar str note: A note recapitulating the every item's dps variance.
    """

    def __init__(self, items, base_dps):
        self.base_dps = base_dps
        self.items = items
        self.upgrade_level = ''
        self.max_upgrade = 0
        self.note = ''
        self.__calculate_upgrade_level()
        self.encounter_id = self.items[0].encounter_id

    def __calculate_upgrade_level(self):
        for item in self.items:
            upgrade_percent = (item.dps_mean / self.base_dps) - 1
            upgrade_percent = upgrade_percent * 100
            self.note += '{:40s} {: 5.0f} ({: 3.0f}%)\n'.format(item.item_slot,
                                                                item.dps_mean - self.base_dps, upgrade_percent)
            if upgrade_percent > self.max_upgrade:
                self.max_upgrade = upgrade_percent
        if self.max_upgrade > 1.0:
            self.upgrade_level = 'B'
        elif self.max_upgrade > 0:
            self.upgrade_level = 'S'


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
ordered_ids = [2458,    2459,    2460,    2461,   2465,
               2470,  2463,     2469,  2457,      2467,   2464]


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
    items = {}
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
        if encounter_id not in items:
            items[encounter_id] = []
        items[encounter_id].append(Item(line))

    output = ""
    # sort upgrades according to ordered_ids
    cells = []
    for encounter_id in ordered_ids:
        if encounter_id == -24:
            continue
        cell = LootCell(items[encounter_id], player_dps)
        cells.append(cell)
    output += results_link_raw
    print('GUARDIAN DAUSEGNE PANTHEON LIHUVIM SKOLEX XY\'MOX HALONDRUS ANDUIN DREADLORDS RYGELON JAILER')
    for cell in cells:
        print(encounter_ids[cell.encounter_id] + ' ' +
              cell.upgrade_level + ' ' + cell.note)
    return cells


def parse_button_wrapper(results_link, treeview, service, username):
    try:
        res = process_results(results_link)
        update_treeview(treeview, res)
        update_existing_data(username, service, treeview)
    except Exception as e:
        messagebox.showerror('shit', 'There was an error: ' + str(e))


def send_button_wrapper(results_link, service, username):
    try:
        res = process_results(results_link)
        row = find_user_row(username, service)
        update_cells(res, service, results_link, row)
        messagebox.showinfo(
            'GOOD', 'Successfully updated the great Prismatic Database. Your information is in good hands.')
    except Exception as e:
        messagebox.showerror('shit', 'There was an error: ' + str(e))


def update_treeview(treeview, items):
    letters = []
    i = 0
    for cell in items:
        letters.append(cell.upgrade_level)
        i += 1
    treeview.item(treeview.get_children()[1], values=tuple(letters))


def update_cells(cells, service, link, row):
    rows = []
    values = []
    for cell in cells:
        values.append(
            {'userEnteredValue': {"stringValue": cell.upgrade_level}, 'note': cell.note})
    values.append({'userEnteredValue': {"stringValue": link}})
    rows.append({'values': values})
    request_body = {
        "updateCells": {
            "range": {
                "sheetId": 273416977,
                "startRowIndex": row - 1,
                "endRowIndex": row,
                "startColumnIndex": 2,
                "endColumnIndex": 14
            },
            "rows": rows,
            "fields": "note,userEnteredValue"
        }
    }
    body = {"requests": [request_body]}
    # dump
    with open('body.json', 'w') as f:
        json.dump(body, f)
    response = service.spreadsheets().batchUpdate(
        spreadsheetId=SAMPLE_SPREADSHEET_ID, body=body).execute()
    print(response)


def auth():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds


def find_user_row(username, service):
    # First, try to find the user's row in the spreadsheet
    request = service.spreadsheets().values().get(
        spreadsheetId=SAMPLE_SPREADSHEET_ID, range=NAMES_RANGE)
    response = request.execute()
    values = response.get('values', [])
    # save username to file for next run
    with open('username.txt', 'w') as f:
        f.write(username)
    if not values:
        print('No data found.')
    else:
        i = 8
        for row in values:
            if len(row) > 0 and row[0] == username:
                return i
            i += 1
    return None


def get_existing_data(range, service):
    # Call the Sheets API
    req = service.spreadsheets().get(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                                     ranges=[range], includeGridData=True)
    response = req.execute()
    with open('sheet.json', 'w') as f:
        json.dump(response, f)

    result = response.get('sheets')[0].get('data')[0].get('rowData')
    values = []
    for row in result:
        for cell in row.get('values'):
            try:
                values.append(
                    cell.get('effectiveValue').get('stringValue'))
            except:
                values.append('')
    return values


def update_existing_data(username, service, treeview):
    row = find_user_row(username, service)
    range = USER_RANGE.format(row, row)
    global USER_RANGE_FORMATTED
    USER_RANGE_FORMATTED = range
    values = get_existing_data(range, service)
    letters = []
    i = 0
    treeview.item(treeview.get_children()[0], values=tuple(values))


def main():
    try:
        creds = auth()
    except Exception as e:
        messagebox.showerror(
            'shit', 'There was an error when trying to log in: ' + str(e))
        return
    try:
        service = build('sheets', 'v4', credentials=creds)
    except HttpError as err:
        print(err)

    # Open a window with the following:
    # * A text box to enter the raidbots link
    # * A text box to enter the username
    # * A button to parse the data
    # * A button to send the data to the database
    # * A row of cells to show the *current* cells from the spreadsheet
    # * A row of cells to show the *potential* new cells from the spreadsheet
    mainwindow = Tk()
    treeview = ttk.Treeview(mainwindow, height=3)
    mainwindow.title('Prismatic Uploader Version 12.0.3.01 (i made that up)')
    mainwindow.resizable(False, False)
    prompt_label = Label(mainwindow, text='Raidbots report link:')
    prompt_label.place(x=10, y=10)
    results_link = StringVar()
    results_link.set(
        '')
    results_link_entry = Entry(mainwindow, textvariable=results_link, width=50)
    results_link_entry.place(x=140, y=10)
    username_label = Label(mainwindow, text='Username:')
    username_label.place(x=10, y=40)
    username = StringVar()
    if os.path.exists('username.txt'):
        with open('username.txt', 'r') as f:
            username.set(f.read())
    username_entry = Entry(mainwindow, textvariable=username, width=50)
    username_entry.place(x=140, y=40)
    parse_button = Button(mainwindow, text='Check', command=lambda: parse_button_wrapper(
        results_link.get(), treeview, service, username.get()))
    parse_button.place(x=150+15, y=70)

    send_button = Button(mainwindow, text='Send', command=lambda: send_button_wrapper(
        results_link=results_link.get(), service=service, username=username.get()))
    send_button.place(x=150+155, y=70)

    treeview['columns'] = tuple(ordered_ids)
    treeview.column('#0', width=70)
    for i, encounter_id in enumerate(ordered_ids):
        treeview.heading(str(encounter_id), text=encounter_ids[encounter_id])
        treeview.column(str(encounter_id), width=50, anchor=CENTER)

    treeview.insert(parent='', index='end', iid=0,
                    text='Current', values=(''))
    treeview.insert(parent='', index='end', iid=1,
                    text='Potential', values=(''))
    treeview.place(x=10, y=120)

    mainwindow.geometry('700x300')
    mainwindow.mainloop()


if __name__ == '__main__':
    main()
