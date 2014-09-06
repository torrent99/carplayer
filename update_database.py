#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# NCMPY - a [Python + Curses]-based MPD client.
# 
# Copyright (C) 2011 Cyker Way
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

'''NCMPY - a [Python + Curses]-based MPD client.'''

import copy, curses
import httplib2
import locale
import mpd
import os
#import pyosd
import re
import select, sys
import time, threading
import urllib
import fnmatch
import os.path
import pickle
import time

from ncmpymodule import lrc, ttplyrics

# ------------------------------
# global configuration
# ------------------------------

# Where conf files lie. Order IS important.
conf_files = [os.path.expanduser('~/.ncmpy/ncmpy.conf'), '/etc/ncmpy.conf']

# global conf
conf = {}

def read_conf():
    '''Read global configurations from file.'''

    conf['MPD_HOST'] = 'localhost'
    conf['MPD_PORT'] = 6600
    conf['ENABLE_OSD'] = False
    conf['ENABLE_RATING'] = False
    conf['LYRICS_DIR'] = os.path.expanduser('~/.ncmpy/lyrics')

    for cf in conf_files:
        if not os.path.isfile(cf):
            continue
        with open(cf, 'rt') as f:
            l_cnt = 0
            for l in f:
                l_cnt += 1
                if l.startswith('#'):
                    continue
                m = re.match(r'(\S+)\s+(\S+)', l)
                if not m:
                    continue
                g = m.groups()
                if g[0] == 'MPD_HOST':
                    conf[g[0]] = g[1]
                elif g[0] == 'MPD_PORT':
                    conf[g[0]] = int(g[1])
                elif g[0] in ['ENABLE_OSD', 'ENABLE_RATING']:
                    conf[g[0]] = g[1].lower() in ['yes', '1']
                elif g[0] == 'LYRICS_DIR':
                    conf[g[0]] = os.path.expanduser(g[1])
                else:
                    raise Exception('Unknows option {a} in conf file {b}, line {c}'.format(a=g[0], b=cf, c=l_cnt))
        break

# ------------------------------
# DON'T modify code below
# ------------------------------

class NCMPY_MOD():
    '''Base class of all mods'''

    def __init__(self, win, main):
        '''Initializer.
        
        Parameters:

            win - curses.window.
            main - main control. NCMPY instance.'''

        self.win = win
        self.main = main
        self.mpc = main.mpc
        self.board = main.board
        self.height, self.width = self.win.getmaxyx()

        self.nsks = []
        self.psks = []

    def udata(self):
        '''Update data.'''
        
        self.status = self.main.status
        self.stats = self.main.stats
        self.currentsong = self.main.currentsong

    def round_one(self, c):
        '''Round one.'''

        pass

    def round_two(self):
        '''Round two.'''

        pass

    def uwin(self):
        '''Update window.'''

        pass

    def _bar_rdis(self, y, x):
        '''Reset display for bar-like windows.'''

        self.win.resize(1, self.main.width)
        self.height, self.width = self.win.getmaxyx()
        self.win.mvwin(y, x)

    def _block_rdis(self):
        '''Reset display for block-like windows.'''

        self.win.resize(self.main.height - 4, self.main.width)
        self.height, self.width = self.win.getmaxyx()
        self.win.mvwin(2, 0)

        self.sel = min(self.sel, self.beg + self.height - 1)

    def rdis(self):
        '''Reset display use _bar_rdis/_block_rdis.'''

        pass

    def _format_time(self, tm):
        '''Convert time: <seconds> -> <hh:mm:ss>.'''

        if tm.isdigit():
            tm = int(tm)
            h, m, s = tm // 3600, (tm // 60) % 60, tm % 60
            return '{hour}:'.format(hour=h) * bool(h > 0) + '{minute:02d}:{sec:02d}'.format(minute=m, sec=s)
            return ''
        else:
            return ''

    def _get_tag(self, tagname, item):
        tag = item.get(tagname)
        if isinstance(tag, str):
            return tag
        elif isinstance(tag, list):
            return ', '.join(tag)
        else:
            return None

    def _validate(self, n):
        '''Constrain value in range [0, num).'''

        return max(min(n, self.num - 1), 0)

    def _search(self, modname, c):
        '''Search in mods.'''

        if modname == 'Queue':
            items = self._queue
        elif modname in ['Database', 'Artist-Album', 'Search']:
            items = self._view

        if self.main.search and self.main.search_di:
            di = {
                    ord('/') : 1, 
                    ord('?') : -1, 
                    ord('n') : self.main.search_di, 
                    ord('N') : -self.main.search_di
                    }[c]
            has_match = False

            for i in [k % len(items) for k in range(self.sel + di, self.sel + di + di * len(items), di)]:
                item = items[i]

                if modname in ['Queue', 'Search']:
                    title = self._get_tag('title', item) or os.path.basename(item['file'])
                elif modname == 'Database':
                    title = item.values()[0]
                elif modname == 'Artist-Album':
                    if self._type in ['artist', 'album']:
                        title = item
                    elif self._type == 'song':
                        title = self._get_tag('title', item) or os.path.basename(item['file'])

                if title.find(self.main.search) != -1:
                    has_match = True
                    if di == 1 and i <= self.sel:
                        self.board['msg'] = 'search hit BOTTOM, continuing at TOP'
                    elif di == -1 and i >= self.sel:
                        self.board['msg'] = 'search hit TOP, continuing at BOTTOM'
                    self.locate(i)
                    break

            if not has_match:
                self.board['msg'] = 'Pattern not found: {thing}'.format(thing=self.main.search)

class NCMPY_SCROLL():
    '''Scrolling interface.
    
    'ns_' means no selection'''

    def __init__(self):
        self.beg = 0
        self.num = 0
        self.cur = 0
        self.sel = 0

    def one_line_down(self):
        if self.sel < self.num - 1:
            self.sel += 1
            if self.sel - self.beg == self.height:
                self.beg += 1

    def one_line_up(self):
        if self.sel > 0:
            self.sel -= 1
            if self.sel - self.beg == -1:
                self.beg -= 1

    def one_page_down(self):
        if self.sel < self.num - self.height:
            self.sel += self.height
            self.beg = min(self.beg + self.height, self.num - self.height)
        else:
            self.sel = self.num - 1
            self.beg = max(self.num - self.height, 0)

    def one_page_up(self):
        if self.sel < self.height:
            self.sel = 0
            self.beg = 0
        else:
            self.sel -= self.height
            self.beg = max(self.beg - self.height, 0)

    def ns_one_line_down(self):
        if self.beg < self.num - self.height:
            self.beg += 1

    def ns_one_line_up(self):
        if self.beg > 0:
            self.beg -= 1

    def ns_one_page_down(self):
        self.beg = min(self.beg + self.height, self.num - self.height)

    def ns_one_page_up(self):
        self.beg = max(self.beg - self.height, 0)

    def to_top(self):
        self.sel = self.beg

    def to_middle(self):
        self.sel = min(self.beg + self.height / 2, self.num - 1)

    def to_bottom(self):
        self.sel = min(self.beg + self.height - 1, self.num - 1)

    def to_begin(self):
        self.beg = 0
        self.sel = 0

    def to_end(self):
        self.beg = max(self.num - 1, 0)
        self.sel = max(self.num - 1, 0)

    def locate(self, pos):
        '''Locate sel at pos, and put in the center.'''

        if pos >= self.height / 2:
            self.beg = pos - self.height / 2
        else:
            self.beg = 0
        self.sel = pos

class NCMPY_MENU(NCMPY_MOD):
    '''Display mod name, play mode and volume.'''

    def __init__(self, win, main):
        NCMPY_MOD.__init__(self, win, main)
        self.win.attron(curses.A_BOLD)

    def _make_mode_str(self):
        '''Prepare mode_str.'''

        blank = ' ' * 5
        return (int(self.status['consume']) and '[con]' or blank) + \
                (int(self.status['random']) and '[ran]' or blank) + \
                (int(self.status['repeat']) and '[rep]' or blank) + \
                (int(self.status['single']) and '[sin]' or blank)

    def _make_menu_str(self):
        #title_str = self.main.tmodname + "Dir Num:" + str(self.main.global_dir_index)
        title_str = "Dir:" + str(self.main.global_dir_index)
        mode_str = self._make_mode_str()
        #vol_str = 'Volume: ' + self.status['volume'] + '%'
        #mode_str = ''
        vol_str = ''
        state_str = '{mode}    {vol}'.format(mode=mode_str, vol=vol_str)
        title_len = self.width - len(state_str)
        return title_str[:title_len].ljust(title_len) + state_str


    def uwin(self):
        menu_str = self._make_menu_str()

        # must use insstr instead of addstr, since addstr cannot 
        # draw to the last character (will raise an exception). 
        # Similar cases follow in other mods.
        self.win.erase()
        self.win.insstr(0, 0, menu_str)
        self.win.noutrefresh()

    def rdis(self):
        self._bar_rdis(0, 0)

class NCMPY_TITLE(NCMPY_MOD):
    '''Hline.'''

    def __init__(self, win, main):
        NCMPY_MOD.__init__(self, win, main)

    def uwin(self):
        self.win.erase()
        self.win.insstr(0, 0, self.width * '-')
        self.win.noutrefresh()

    def rdis(self):
        self._bar_rdis(1, 0)

class NCMPY_PROGRESS(NCMPY_MOD):
    '''Show playing progress.'''

    def __init__(self, win, main):
        NCMPY_MOD.__init__(self, win, main)

    def _make_prog_str(self):
        '''Prepare prog_str.'''

        # no 'time' option in mpd's status if stopped
        tm = self.status.get('time')
        if tm:
            elapsed, total = tm.split(':')
            if float(total) <= 0:
                total = 9999
            pos = int((float(elapsed) / float(total)) * (self.width - 1))
            return '=' * pos + '0' + '-' * (self.width - pos - 1)
        else:
            return '-' * self.width

    def uwin(self):
        prog_str = self._make_prog_str()

        self.win.erase()
        self.win.insstr(0, 0, prog_str)
        self.win.noutrefresh()

    def rdis(self):
        self._bar_rdis(self.main.height - 2, 0)

class NCMPY_STATUS(NCMPY_MOD):
    '''Show playing status, elapsed/total time.'''

    def __init__(self, win, main):
        NCMPY_MOD.__init__(self, win, main)
        self._state_name = {
                'play' : 'Playing',
                'stop' : 'Stopped',
                'pause' : 'Paused',
                }
        self.win.attron(curses.A_BOLD)

    def _make_title_str(self):
        '''Prepare title_str.'''

        song = self.currentsong
        title = song and (song.get('title') or os.path.basename(song.get('file'))) or ''
        return '{freeda}'.format(freeda=title)

    def _make_artist_str(self):
        '''Prepare title_str.'''

        song = self.currentsong
        artist = song and (song.get('artist') or os.path.basename(song.get('file'))) or ''
        return '{freeda}'.format(freeda=artist)

    def _make_tm_str(self):
        '''Prepare tm_str.'''

        tm = self.status.get('time') or '0:0'
        elapsed, total = tm.split(':')
        elapsed, total = int(elapsed), int(total)
        elapsed_mm, elapsed_ss, total_mm, total_ss = elapsed / 60, elapsed % 60, total / 60, total % 60
        return '[{0}:{1:02d} ~ {2}:{3:02d}]'.format(elapsed_mm, elapsed_ss, total_mm, total_ss)

    def uwin(self):
        # use two strs because it's difficult to calculate 
        # display length of unicode characters
        title_str = self._make_title_str()
        artist_str = self._make_artist_str()
        tm_str = self._make_tm_str()
        play_state = str(self._state_name[self.status['state']])

        self.win.erase()
        self.win.insstr(0, 0, artist_str)
        self.win.insstr(0, self.width - len(play_state), play_state)
        self.win.insstr(1, 0, title_str)
        self.win.insstr(1, self.width - len(tm_str), tm_str)
        self.win.noutrefresh()

    def rdis(self):
        self._bar_rdis(self.main.height - 1, 0)

class NCMPY_MESSAGE(NCMPY_MOD):
    '''Show message and get user input.'''

    def __init__(self, win, main):
        NCMPY_MOD.__init__(self, win, main)
        self._msg = None
        self._timeout = 0

    def getstr(self, prompt):
        '''Get user input with prompt <prompt>.'''

        curses.nocbreak()
        curses.echo()
        curses.curs_set(1)
        self.win.move(0, 0)
        self.win.clrtoeol()
        self.win.addstr('{prompt}: '.format(prompt=prompt), curses.A_BOLD)
        s = self.win.getstr(0, len(prompt) + 2)
        curses.curs_set(0)
        curses.noecho()
        curses.cbreak()
        return s

    def uwin(self):
        msg = self.board.get('msg')
        if msg:
            self._msg = msg
            self._timeout = 5

        if self._timeout > 0:
            self.win.erase()
            self.win.insstr(0, 0, self._msg, curses.A_BOLD)
            self.win.noutrefresh()
            self._timeout -= 1

    def rdis(self):
        self._bar_rdis(self.main.height - 1, 0)

class NCMPY_HELP(NCMPY_MOD, NCMPY_SCROLL):
    '''Help.'''

    def __init__(self, win, main):
        NCMPY_MOD.__init__(self, win, main)
        NCMPY_SCROLL.__init__(self)
        self._options = [
                ('group', 'Global', None), 
                ('hline', None, None), 
                ('item', 'F7', 'Help'), 
                ('item', 'F2', 'Queue'), 
                ('item', 'F3', 'Database'), 
                ('item', 'F4', 'Lyrics'), 
                ('item', 'F5', 'Artist-Album'), 
                ('item', 'F6', 'Search'), 
                ('blank', None, None), 
                ('item', 'q', 'quit'), 
                ('blank', None, None), 

                ('group', 'Playback', None), 
                ('hline', None, None), 
                ('item', 'Space', 'Play/Pause'), 
                ('item', 's', 'Stop'), 
                ('item', '>', 'next song'), 
                ('item', '<', 'previous song'), 
                ('blank', None, None), 
                ('item', 'u', 'consume mode'), 
                ('item', 'i', 'random mode'), 
                ('item', 'o', 'repeat mode'), 
                ('item', 'p', 'single mode'), 
                ('blank', None, None), 
                ('item', '9', 'volume down'), 
                ('item', '0', 'volume up'), 
                ('blank', None, None), 
                ('item', 'left', 'seek +1'), 
                ('item', 'right', 'seek -1'), 
                ('item', 'down', 'seek -1%'), 
                ('item', 'up', 'seek +1%'), 
                ('blank', None, None), 

                ('group', 'Movement', None), 
                ('hline', None, None), 
                ('item', 'j', 'go one line down'), 
                ('item', 'k', 'go one line up'), 
                ('item', 'f', 'go one page down'), 
                ('item', 'b', 'go one page up'), 
                ('item', 'g', 'go to top of list'), 
                ('item', 'G', 'go to bottom of list'), 
                ('item', 'H', 'go to top of screen'), 
                ('item', 'M', 'go to middle of screen'), 
                ('item', 'L', 'go to bottom of screen'), 
                ('blank', None, None), 
                ('item', '/', 'search down'), 
                ('item', '?', 'search up'), 
                ('item', 'n', 'next match'), 
                ('item', 'N', 'previous match'), 
                ('blank', None, None), 

                ('group', 'Queue', ''), 
                ('hline', None, None), 
                ('item', 'Enter', 'Play'), 
                ('item', 'l', 'select and center current song'), 
                ('item', '\'', 'toggle auto center'), 
                ('item', ';', 'locate selected song in database'), 
                ('item', 'h', 'get info about current/selected song'), 
                ('blank', None, None), 
                ('item', '1', 'rate selected song as     *'), 
                ('item', '2', 'rate selected song as    **'), 
                ('item', '3', 'rate selected song as   ***'), 
                ('item', '4', 'rate selected song as  ****'), 
                ('item', '5', 'rate selected song as *****'), 
                ('blank', None, None), 
                ('item', 'J', 'Move down selected song'), 
                ('item', 'K', 'Move up selected song'), 
                ('item', 'e', 'shuffle queue'), 
                ('item', 'c', 'clear queue'), 
                ('item', 'a', 'add all songs from database'), 
                ('item', 'd', 'delete selected song from queue'), 
                ('item', 'S', 'save queue to playlist'), 
                ('item', 'O', 'load queue from playlist'), 
                ('blank', None, None), 

                ('group', 'Database', ''), 
                ('hline', None, None), 
                ('item', 'Enter', 'open directory / append to queue (if not existing yet) and play / load playlist'), 
                ('item', '\'', 'go to parent directory'), 
                ('item', '"', 'go to root directory'), 
                ('item', 'a', 'append song to queue recursively'), 
                ('item', ';', 'locate selected song in queue'), 
                ('item', 'h', 'get info about selected song'), 
                ('item', 'U', 'update database'), 
                ('blank', None, None), 

                ('group', 'Lyrics', ''), 
                ('hline', None, None), 
                ('item', 'l', 'center current line'), 
                ('item', '\'', 'toggle auto center'), 
                ('item', 'K', 'save lyrics'), 
                ('blank', None, None), 

                ('group', 'Artist-Album', ''), 
                ('hline', None, None), 
                ('item', 'Enter', 'open level / append to queue (if not existing yet) and play'), 
                ('item', '\'', 'go to parent level'), 
                ('item', '"', 'go to root level'), 
                ('item', 'a', 'append song to queue recursively'), 
                ('item', ';', 'locate selected song in queue'), 
                ('blank', None, None), 

                ('group', 'Search', ''), 
                ('hline', None, None), 
                ('item', 'B', 'start a database search, syntax = <tag_name>:<tag_value>'), 
                ('item', 'Enter', 'append to queue (if not existing yet) and play'), 
                ('item', 'a', 'append to queue'), 
                ('item', ';', 'locate selected song in queue'), 
                ('blank', None, None), 

                ('group', 'Info', ''), 
                ('hline', None, None), 
                ('item', 'h', 'back to previous window'), 
                ('blank', None, None), 
                ]
        self.num = len(self._options)

    def round_one(self, c):
        if c == ord('j'):
            self.ns_one_line_down()
        elif c == ord('k'):
            self.ns_one_line_up()
        elif c == ord('f'):
            self.ns_one_page_down()
        elif c == ord('b'):
            self.ns_one_page_up()

    def uwin(self):
        self.win.erase()
        for i in range(self.beg, min(self.beg + self.height, self.num)):
            line = self._options[i]
            if line[0] == 'group':
                self.win.insstr(i - self.beg, 6, line[1], curses.A_BOLD)
            elif line[0] == 'hline':
                self.win.attron(curses.A_BOLD)
                self.win.hline(i - self.beg, 3, '-', self.width - 6)
                self.win.attroff(curses.A_BOLD)
            elif line[0] == 'item':
                self.win.insstr(i - self.beg, 0, line[1].rjust(20) + ' : ' + line[2])
            elif line[0] == 'blank':
                pass
        self.win.noutrefresh()

    def rdis(self):
        self._block_rdis()

class NCMPY_QUEUE(NCMPY_MOD, NCMPY_SCROLL):
    '''Queue = current playlist.'''

    def __init__(self, win, main):
        NCMPY_MOD.__init__(self, win, main)
        NCMPY_SCROLL.__init__(self)

        self.nsks = [ord('l'), ord('\'')]
        self.psks = [ord('d'), ord('J'), ord('K')]

        # playlist version
        self._version = -1

        # auto-center
        self._auto_center = False

    def udata(self):
        NCMPY_MOD.udata(self)
        
        if self.main.c in self.main.allpsks:
            return

        # fetch playlist if version is different
        if self._version != int(self.main.status['playlist']):
            self._queue = self.mpc.playlistinfo()
            self.num = len(self._queue)
            self.beg = self._validate(self.beg)
            self.sel = self._validate(self.sel)
            # self.cur is set later, so not validated here

            for song in self._queue:
		rating = 0
                if conf['ENABLE_RATING']:
                    try:
                        rating = int(self.mpc.sticker_get('song', song['file'], 'rating').split('=',1)[1])
                    except mpd.CommandError:
                        rating = 0
                    finally:
                        song['rating'] = rating
                else:
                    song['rating'] = 0

            self._version = int(self.status['playlist'])

        self.cur = self.status.has_key('song') and int(self.status['song']) or 0

    def round_one(self, c):
        if c == ord('j'):
            self.one_line_down()
        elif c == ord('k'):
            self.one_line_up()
        elif c == curses.KEY_DOWN:
            self.one_line_down()
        elif c == curses.KEY_UP:
            self.one_line_up()
        elif c == ord('f'):
            self.one_page_down()
        elif c == ord('b'):
            self.one_page_up()
        elif c == ord('H'):
            self.to_top()
        elif c == ord('M'):
            self.to_middle()
        elif c == ord('L'):
            self.to_bottom()
        elif c == ord('g'):
            self.to_begin()
        elif c == ord('G'):
            self.to_end()
        elif c == ord('l'):
            self.locate(self.cur)
        elif c == ord('a'):
            self.mpc.add('')
        elif c == ord('c'):
            self.mpc.clear()
            self.num, self.beg, self.sel, self.cur = 0, 0, 0, 0
        elif c == ord('d'):
            if self.num > 0:
                self.main.pending.append('deleteid({d})'.format(d=self._queue[self.sel]['id']))
                self._queue.pop(self.sel)
                if self.sel < self.cur:
                    self.cur -= 1
                self.num -= 1
                self.beg = self._validate(self.beg)
                self.sel = self._validate(self.sel)
                self.cur = self._validate(self.cur)
        elif c == ord('J'):
            if self.sel + 1 < self.num:
                self.main.pending.append('swap({bib}, {bob})'.format(bib=self.sel, bob=self.sel + 1))
                self._queue[self.sel], self._queue[self.sel + 1] = self._queue[self.sel + 1], self._queue[self.sel]
                if self.cur == self.sel:
                    self.cur += 1
                elif self.cur == self.sel + 1:
                    self.cur -= 1
                self.one_line_down()
        elif c == ord('K'):
            if self.sel > 0:
                self.main.pending.append('swap({bib}, {bob})'.format(bib=self.sel, bob=self.sel - 1))
                self._queue[self.sel - 1], self._queue[self.sel] = self._queue[self.sel], self._queue[self.sel - 1]
                if self.cur == self.sel - 1:
                    self.cur += 1
                elif self.cur == self.sel:
                    self.cur -= 1
                self.one_line_up()
        elif c == ord('e'):
            self.mpc.shuffle()
        elif c == ord('\n'):
            self.mpc.playid(self._queue[self.sel]['id'])
        elif c == curses.KEY_RIGHT:
            self.mpc.playid(self._queue[self.sel]['id'])
        elif c in range(ord('1'), ord('5') + 1):
            if conf['ENABLE_RATING']:
                rating = c - ord('0')
                song = self._queue[self.cur]
                self.mpc.sticker_set('song', song['file'], 'rating', rating)
                song['rating'] = rating
        elif c in [ord('/'), ord('?'), ord('n'), ord('N')]:
            self._search('Queue', c)
        elif c == ord('\''):
            self._auto_center = not self._auto_center
        elif c == ord(';'):
            self.board['path'] = self._queue[self.sel]['file']

            

        # set q_sel in shared memory (INFO mod will use)
        if self.num > 0:
            self.board['q_sel'] = self._queue[self.sel]
            

    def round_two(self):
        uri = self.board.get('locate')
        if uri:
            for i in range(len(self._queue)):
                if uri == self._queue[i]['file']:
                    self.locate(i)
                    break
            else:
                self.board['msg'] = 'Not found in playlist'

        # auto center
        if self._auto_center:
            self.locate(self.cur)

    def uwin(self):
        self.win.erase()
        for i in range(self.beg, min(self.beg + self.height, self.num)):
            item = self._queue[i]
            title = self._get_tag('title', item) or os.path.basename(item['file'])
            rating = item['rating']
            if item.has_key('time'):
                temp_time = str(item['time'])
            else:
                temp_time = str(0)
            tm = self._format_time(temp_time)

            if i == self.cur:
                self.win.attron(curses.color_pair(2) | curses.A_BOLD)
            if i == self.sel:
                self.win.attron(curses.color_pair(3) | curses.A_REVERSE)
                self.win.attron(curses.A_REVERSE)
            self.win.hline(i - self.beg, 0, ' ', self.width)
            self.win.addnstr(i - self.beg, 0, title, self.width - 18)
            self.win.addnstr(i - self.beg, self.width - 16, rating * '*', 5)
            self.win.insstr(i - self.beg, self.width - len(tm), tm)
            if i == self.sel:
                self.win.attroff(curses.color_pair(3) | curses.A_REVERSE)
            if i == self.cur:
                self.win.attroff(curses.color_pair(2) | curses.A_BOLD)
                #self.win.attroff(curses.A_BOLD)
        self.win.noutrefresh()

    def rdis(self):
        self._block_rdis()

class NCMPY_DATABASE(NCMPY_MOD, NCMPY_SCROLL):
    '''All songs/directories/playlists in database.'''

    def __init__(self, win, main):
        NCMPY_MOD.__init__(self, win, main)
        NCMPY_SCROLL.__init__(self)

        # current displayed dir
        self._dir = ''
        self._dir_index = 1
        self.directory_database = [[0,"/mnt/Music"]]
        self.file_database = [[0,0,0,"/mnt/Music"]]
        self.includes = ['*.mp3', '*.wav', '*.MP3', '*.ogg', '*.flac', '*.aac', '*.wma', '*.WMA'] # for files only
        #self.excludes = ['/home/paulo-freitas/Documents'] # for dirs and files

        # transform glob patterns to regular expressions
        self.includes = r'|'.join([fnmatch.translate(x) for x in self.includes])
        #self.excludes = r'|'.join([fnmatch.translate(x) for x in self.excludes]) or r'$.'
        #path = "/mnt/rec1/Music/"

        self.directory_index = 21
        self.file_index = 1
        try:
           database_file = open('carplayer.database')
           self.directory_database = pickle.load(database_file)
           #self.file_database = pickle.load(database_file)
           database_file.close()
        except IOError:
              print 'Oh dear.'
              #self.mpc.update()
              self.add_mpd_directory_to_database('')
              database_file = open('carplayer.database',"w")
              pickle.dump(self.directory_database,database_file)
              #pickle.dump(self.file_database,database_file)
              database_file.close()
              curses.endwin()
              exit(0)
              
        self._view = self._build_view()

   
    def count_songs_in_directory(self, dir_list):
        song_count = 0
        for item in dir_list:
            if item.has_key('file'):
                uri = item['file']
                if self.is_file_music_type(uri):
                    song_count += 1
        return song_count 
        

    def add_mpd_directory_to_database(self, mpd_dir):
        dir_list = self.mpc.lsinfo(mpd_dir)
       
        dir_song_count = self.count_songs_in_directory(dir_list)

        if dir_song_count > 0:
            self.directory_database.append([self.directory_index,mpd_dir])
            self.directory_index += 1
        self.album_file_index = 1

        for item in dir_list:
            if item.has_key('directory'):
                uri = item['directory']
                self.add_mpd_directory_to_database(uri)
            elif item.has_key('file'):
                uri = item['file']
                self.file_database.append([self.directory_index,self.file_index,self.album_file_index,uri])
                self.file_index += 1
                self.album_file_index += 1

    def num_from_string(self,s):
        try:
            return int(s)
        except ValueError:
            return 1

    def find_directory_from_index(self,index):
        result = ''
        index = self.num_from_string(index)
        if index <= 0:
           index = 1
        for i in range(len(self.directory_database)):
             dir_item = self.directory_database[i]
             dir_index = dir_item[0]
             if index == dir_index:
                result = dir_item[1]
                break
        return result
        
    def find_directory_number(self,uri):
        result = " "

        try:
            i = [x[1] for x in self.directory_database].index(uri)
            result = self.directory_database[i][0]
        except:
            result = " "
        return result

        #for i in range(len(self.directory_database)):
        #     dir_item = self.directory_database[i]
        #     dir_path = dir_item[1]
        #     if uri == dir_path:
        #        result = dir_item[0]
        #        break
        #return result
        
    def is_file_music_type(self, uri):
        if re.match(self.includes, uri):
              result = True
        else:
              result = False
        return result
 
    def jump_and_play_uri(self, dir_uri):
            self._dir = dir_uri
            self._view = self._build_view()
            item = self._view[self.sel]
            while item.has_key('directory'):
                self.one_line_down()
                item = self._view[self.sel]
            uri = item['file']
            self.mpc.clear()
            #self.mpc.add(os.path.dirname(self._dir))
            self.mpc.add(self._dir)
            song = self.mpc.playlistfind('file', uri)[0]
            self.mpc.playid(song['id'])


    def _build_view(self, keeppos=False):
        '''Build view using self._dir.
        
        A view is rebuilt when self._dir changes (ex. database update), 
        or new items are added/removed (ex. playlist add/delete).'''

        self.main.global_dir_index = self.find_directory_number(self._dir)
        view = self.mpc.lsinfo(self._dir)
        #view.insert(0, {'directory' : '..'})
        self.num = len(view)
        if keeppos:
            self.beg = self._validate(self.beg)
            self.sel = self._validate(self.sel)
        else:
            self.beg = 0
            self.sel = 0
        for i in range(len(view)):
           item = view[i]
           if item.has_key('directory'):
               uri = item['directory']
               view[i]['directory_id'] = self.find_directory_number(uri)

        return view

    def udata(self):
        NCMPY_MOD.udata(self)
        
        if self.board.get('main-database') == 'updated':
            self._dir = ''
            self._view = self._build_view()
            self.board['msg'] = 'Database updated'

    def round_one(self, c):
        if c == ord('j'):
            self.one_line_down()
        elif c == ord('k'):
            self.one_line_up()
        elif c == ord('f'):
            self.one_page_down()
        elif c == curses.KEY_DOWN:
            self.one_line_down()
        elif c == curses.KEY_UP:
            self.one_line_up()
        elif c == ord('b'):
            self.one_page_up()
        elif c == ord('H'):
            self.to_top()
        elif c == ord('M'):
            self.to_middle()
        elif c == ord('L'):
            self.to_bottom()
        elif c == ord('g'):
            self.to_begin()
        elif c == ord('G'):
            self.to_end()
        #elif c == ord('\''):
        elif c == curses.KEY_LEFT:
            old_dir = self._dir
            self._dir = os.path.dirname(self._dir)
            self._view = self._build_view()
            for i in range(len(self._view)):
                if self._view[i].get('directory') == old_dir:
                    self.locate(i)
                    break
        elif c == ord('"'):
            self._dir = ''
            self._view = self._build_view()

        elif c == curses.KEY_RIGHT or c == ord('\n'):
            item = self._view[self.sel]
            if item.has_key('directory'):
                uri = item['directory']
                if uri == '..':
                    old_dir = self._dir
                    self._dir = os.path.dirname(self._dir)
                    self._view = self._build_view()
                    for i in range(len(self._view)):
                        if self._view[i].get('directory') == old_dir:
                            self.locate(i)
                            break
                else:
                    self._dir = uri
                    self._view = self._build_view()

            elif item.has_key('file'):
                uri = item['file']
                songs = self.mpc.playlistfind('file', uri)
                if songs:
                    self.mpc.playid(songs[0]['id'])
                else:
                    self.mpc.add(self._dir)
                    song = self.mpc.playlistfind('file', uri)[0]
                    self.mpc.playid(song['id'])
            elif item.has_key('playlist'):
                name = item['playlist']
                try:
                    self.mpc.load(name)
                except mpd.CommandError as e:
                    self.board['msg'] = str(e).rsplit('} ')[1]
                else:
                    self.board['msg'] = 'Playlist {bib} loaded'.format(bib=name)
        elif c == ord('a'):
            item = self._view[self.sel]
            if item.has_key('directory'):
                uri = item['directory']
            else:
                uri = item['file']
            if uri == '..':
                self.mpc.add(os.path.dirname(self._dir))
            else:
                self.mpc.add(uri)
        elif c == ord('d'):
            item = self._view[self.sel]
            if item.has_key('playlist'):
                name = item['playlist']
                try:
                    self.mpc.rm(name)
                except mpd.CommandError as e:
                    self.board['msg'] = str(e).rsplit('} ')[1]
                else:
                    self.board['msg'] = 'Playlist {bib} deleted'.format(bib=name)
                    self._view = self._build_view(keeppos=True)
        elif c == ord('U'):
            self.mpc.update()
            print 'Sent Update message to daemon'
            self.board['msg'] = 'Sent Update message to daemon'
        elif c in [ord('/'), ord('?'), ord('n'), ord('N')]:
            self._search('Database', c)
        elif c == ord(';'):
            # tell QUEUE we want to locate a song
            item = self._view[self.sel]
            if item.has_key('file'):
                self.board['locate'] = item.get('file')
            else:
                self.board['msg'] = 'No song selected'
        elif c == ord('8'):
            current_dir_index = self.find_directory_number(self._dir)
            if current_dir_index == " ":
               current_dir_index = 1
            current_dir_index += 1
            if current_dir_index > len(self.directory_database):
                current_dir_index = 1
            directory_jump_uri = self.find_directory_from_index(current_dir_index)
            self.jump_and_play_uri(directory_jump_uri)
        elif c == ord('2'):
            current_dir_index = self.find_directory_number(self._dir)
            if current_dir_index == " ":
               current_dir_index = 2
            current_dir_index -= 1
            if current_dir_index == 0:
                current_dir_index = len(self.directory_database)-1
            directory_jump_uri = self.find_directory_from_index(current_dir_index)
            self.jump_and_play_uri(directory_jump_uri)

        elif c == ord('9'):
            current_dir_index = self.find_directory_number(self._dir)
            if current_dir_index == " ":
               current_dir_index = 1
            current_dir_index += 10
            if current_dir_index > len(self.directory_database):
                current_dir_index = current_dir_index - len(self.directory_database)
            directory_jump_uri = self.find_directory_from_index(current_dir_index)
            self.jump_and_play_uri(directory_jump_uri)
        elif c == ord('3'):
            current_dir_index = self.find_directory_number(self._dir)
            if current_dir_index == " ":
               current_dir_index = 2
            current_dir_index -= 10
            if current_dir_index < 1:
                current_dir_index = len(self.directory_database)-1 + current_dir_index
            directory_jump_uri = self.find_directory_from_index(current_dir_index)
            self.jump_and_play_uri(directory_jump_uri)

        # set d_sel in shared memory (INFO mod will use)
        self.board['d_sel'] = self._view[self.sel].get('file')

    def round_two(self):
        # if there's a path request, rebuild view, using 
        # dirname(path) as display root, and search for the 
        # requested song.
        uri = self.board.get('path')
        if uri:
            self._dir = os.path.dirname(uri)
            self._view = self._build_view()
            for i in range(len(self._view)):
                if self._view[i].get('file') == uri:
                    self.locate(i)
                    break
            else:
                self.board['msg'] = 'Not found in database'

        # if a playlist is saved, rebuild view, keep original positions
        if self.board.get('main-playlist') == 'saved':
            self._view = self._build_view(keeppos=True)

    def uwin(self):
        self.win.erase()
        for i in range(self.beg, min(self.beg + self.height, self.num)):
            item = self._view[i]
            if item.has_key('directory'):
                t, uri = 'directory', item['directory']
            elif item.has_key('file'):
                t, uri = 'file', item['file']
            elif item.has_key('playlist'):
                t, uri = 'playlist', item['playlist']

            if item.has_key('directory_id'):
                dir_id = str(item['directory_id'])
            else:
                dir_id = ' '

            if i == self.sel:
                self.win.attron(curses.A_REVERSE)
            if t == 'directory':
                self.win.attron(curses.color_pair(1) | curses.A_BOLD)
            elif t == 'playlist':
                self.win.attron(curses.color_pair(2) | curses.A_BOLD)
            self.win.hline(i - self.beg, 0, ' ', self.width)
            self.win.insstr(i - self.beg, 5, os.path.basename(uri))
            #directory_number = str(self.find_directory_number(uri))
            directory_number = " "
            self.win.insstr(i - self.beg, 1, dir_id)
            if t == 'directory':
                self.win.attroff(curses.color_pair(1) | curses.A_BOLD)
            elif t == 'playlist':
                self.win.attroff(curses.color_pair(2) | curses.A_BOLD)
            if i == self.sel:
                self.win.attroff(curses.A_REVERSE)
        self.win.noutrefresh()

    def rdis(self):
        self._block_rdis()

class NCMPY_LYRICS(NCMPY_MOD, NCMPY_SCROLL, threading.Thread):
    '''Display lyrics.'''

    def __init__(self, win, main):
        NCMPY_MOD.__init__(self, win, main)
        NCMPY_SCROLL.__init__(self)
        threading.Thread.__init__(self, name='lyrics')

        # directory to save lyrics. 
        # Make sure have write permission.
        self._lyrics_dir = conf['LYRICS_DIR']

        # new song, maintained by module
        self._nsong = None
        # old song, maintained by worker
        self._osong = None
        # title of lyrics to fetch
        self._title = None
        # artist of lyrics to fetch
        self._artist = None
        # current lyrics, oneline str
        self._lyrics = '[00:00.00]Cannot fetch lyrics (No artist/title).'
        # current lyrics timestamp as lists, used by main thread only
        self._ltimes = []
        # current lyrics text as lists, used by main thread only
        self._ltexts = []
        # incicate lyrics state: 'local', 'net', 'saved' or False
        self._lyrics_state = False
        # condition variable for lyrics fetching and display
        self._cv = threading.Condition()

        # auto-center
        self._auto_center = True

        # osd engine
        #if conf['ENABLE_OSD']:
            #self._osd = pyosd.osd(font='-misc-droid sans mono-medium-r-normal--0-0-0-0-m-0-iso8859-1', 
                    #colour='#FFFF00', 
                    #align=pyosd.ALIGN_CENTER, 
                    #pos=pyosd.POS_TOP, 
                    #timeout=-1)
            # remembered for osd
            #self._osdcur = -1

    def _transtag(self, tag):
        '''Transform tag into format used by lrc engine.'''

        if tag is None:
            return None
        else:
            return tag.replace(' ', '').lower()

    def udata(self):
        NCMPY_MOD.udata(self)

        song = self.currentsong

        # do nothing if cannot acquire lock
        if self._cv.acquire(blocking=False):
            self._nsong = song.get('file')
            # if currengsong changes, wake up worker
            if self._nsong != self._osong:
                self._artist = song.get('artist')
                self._title = song.get('title')
                self._cv.notify()
            self._cv.release()

    def _save_lyrics(self):
        if self._artist and self._title and self._cv.acquire(blocking=False):
            with open(os.path.join(self._lyrics_dir, self._artist.replace('/', '_') + '-' + self._title.replace('/', '_') + '.lrc'), 'wt') as f:
                f.write(self._lyrics)
            self.board['msg'] = 'Lyrics {bib}-{bob}.lrc saved.'.format(bib=self._artist, bob=self._title)
            self._lyrics_state = 'saved'
            self._cv.release()
        else:
            self.board['msg'] = 'Lyrics saving failed.'

    def round_one(self, c):
        if c == ord('j'):
            self.ns_one_line_down()
        elif c == ord('k'):
            self.ns_one_line_up()
        elif c == ord('f'):
            self.ns_one_page_down()
        elif c == ord('b'):
            self.ns_one_page_up()
        elif c == ord('l'):
            self.locate(self.cur)
        elif c == ord('\''):
            self._auto_center = not self._auto_center
        elif c == ord('K'):
            self._save_lyrics()

    def _parse_lrc(self, lyrics):
        '''Parse lrc lyrics into ltimes and ltexts.'''

        tags, tms = lrc.parse(lyrics)
        sorted_keys = sorted(tms.keys())
        ltimes = [int(i) for i in sorted_keys]
        ltexts = [tms.get(i) for i in sorted_keys]
        return ltimes, ltexts

    def current_line(self):
        '''Calculate line number of current progress.'''

        cur = 0
        tm = self.status.get('time')
        if tm:
            elapsed = int(tm.split(':')[0])
            while cur < self.num and self._ltimes[cur] <= elapsed:
                cur += 1
            cur -= 1
        return cur

    def round_two(self):
        # output 'Updating...' if cannot acquire lock
        if self._cv.acquire(blocking=0):
            # if worker reports lyrics fetched
            if self._lyrics_state in ['local', 'net']:
                # parse lrc (and copy lrc from shared mem to non-shared mem)
                self._ltimes, self._ltexts = self._parse_lrc(self._lyrics)
                self.num, self.beg = len(self._ltimes), 0

                # auto-save lyrics
                if self._lyrics_state == 'net' and self.num > 10:
                    self._save_lyrics()
                else:
                    self._lyrics_state = 'saved'

                if conf['ENABLE_OSD']:
                    self._osdcur = -1
            self._cv.release()
        else:
            self._ltimes, self._ltexts = [0], ['Updating...']
            # set self.num and self.beg
            self.num, self.beg = 1, 0

        # set self.cur, the highlighted line
        self.cur = self.current_line()

        # auto center
        if self._auto_center:
            self.locate(self.cur)

    def uwin(self):
        self.win.erase()
        attr = curses.A_BOLD | curses.color_pair(3)
        for i in range(self.beg, min(self.beg + self.height, self.num)):
            if i == self.cur:
                self.win.insstr(i - self.beg, 0, self._ltexts[i], attr)
            else:
                self.win.insstr(i - self.beg, 0, self._ltexts[i])
        self.win.noutrefresh()

        # osd lyrics if ENABLE_OSD is True
        if conf['ENABLE_OSD']:
            if self.cur != self._osdcur:
                self._osd.hide()
                if self._ltexts:
                    self._osd.display(self._ltexts[self.cur])
                self._osdcur = self.cur

    def run(self):
        self._cv.acquire()
        while True:
            # wait if currentsong doesn't change
            while self._nsong == self._osong:
                self._cv.wait()

            self._lyrics = '[00:00.00]Cannot fetch lyrics (No artist/title).'
            self._lyrics_state = 'local'

            # fetch lyrics if required information is provided
            if self._artist and self._title:
                # try to fetch from local lrc
                lyrics_file = os.path.join(self._lyrics_dir, self._artist.replace('/', '_') + '-' + self._title.replace('/', '_') + '.lrc')
                if os.path.isfile(lyrics_file):
                    with open(lyrics_file, 'rt') as f:
                        self._lyrics = f.read()
                    # inform round_two: lyrics has been fetched
                    self._lyrics_state = 'local'
                # if local lrc doesn't exist, fetch from Internet
                else:
                    self._lyrics = ttplyrics.fetch_lyrics(self._transtag(self._artist), self._transtag(self._title))
                    # inform round_two: lyrics has been fetched
                    self._lyrics_state = 'net'
            self._osong = self._nsong

    def rdis(self):
        self._block_rdis()

class NCMPY_INFO(NCMPY_MOD, NCMPY_SCROLL):
    '''Information about songs:
    
        currently playing
        currently selected in queue
        currently selected in database'''

    def __init__(self, win, main):
        NCMPY_MOD.__init__(self, win, main)
        NCMPY_SCROLL.__init__(self)
        self._prevtmodname = None
        # current playing
        self._cp = {}
        # selected in queue
        self._siq = {}
        # selected in database
        self._sid = {}
        # database.sel's uri cache
        self._dburi = None
        self._options = [
                ('group', 'Currently Playing', None), 
                ('hline', None, None), 
                ('item', 'Title', ''), 
                ('item', 'Artist', ''), 
                ('item', 'Album', ''), 
                ('item', 'Track', ''), 
                ('item', 'Genre', ''), 
                ('item', 'Date', ''), 
                ('item', 'Time', ''), 
                ('item', 'File', ''), 
                ('blank', None, None), 

                ('group', 'Currently Selected in Queue', None), 
                ('hline', None, None), 
                ('item', 'Title', ''), 
                ('item', 'Artist', ''), 
                ('item', 'Album', ''), 
                ('item', 'Track', ''), 
                ('item', 'Genre', ''), 
                ('item', 'Date', ''), 
                ('item', 'Time', ''), 
                ('item', 'File', ''), 
                ('blank', None, None), 

                ('group', 'Currently Selected in Database', None), 
                ('hline', None, None), 
                ('item', 'Title', ''), 
                ('item', 'Artist', ''), 
                ('item', 'Album', ''), 
                ('item', 'Track', ''), 
                ('item', 'Genre', ''), 
                ('item', 'Date', ''), 
                ('item', 'Time', ''), 
                ('item', 'File', ''), 
                ('blank', None, None), 

                ('group', 'MPD Statistics', None), 
                ('hline', None, None), 
                ('item', 'NumberofSongs', ''), 
                ('item', 'NumberofArtists', ''), 
                ('item', 'NumberofAlbums', ''), 
                ('item', 'Uptime', ''), 
                ('item', 'Playtime', ''), 
                ('item', 'DBPlaytime', ''), 
                ('item', 'DBUpdateTime', ''), 
                ('blank', None, None), 
                ]
        self._options_d = None
        self._song_key_list = ['Title', 'Artist', 'Album', 'Track', 'Genre', 'Date', 'Time', 'File']
        self._stats_key_list = ['Songs', 'Artists', 'Albums', 'Uptime', 'Playtime', 'DB_Playtime', 'DB_Update']

    def round_one(self, c):
        if c == ord('j'):
            self.ns_one_line_down()
        elif c == ord('k'):
            self.ns_one_line_up()
        elif c == ord('f'):
            self.ns_one_page_down()
        elif c == ord('b'):
            self.ns_one_page_up()
        elif c == ord('h'):
            if self._prevtmodname:
                self.board['i_back'] = self._prevtmodname

    def round_two(self):
        if self.board.has_key('prevtmodname'):
            self._prevtmodname = self.board['prevtmodname']

        # get song info.

        # cp = currently playing
        # siq = selected in queue
        # sid = selected in database

        # on success, _cp and _siq are nonempty dicts.
        # on failure, _cp and _siq are empty dicts.
        self._cp = self.currentsong
        try:
            self._siq = self.board.get('q_sel') or {}
        except (mpd.CommandError, IndexError):
            self._siq = {}
        try:
            uri = self.board.get('d_sel')
            if uri and uri != self._dburi and not self.main.idle:
                self._sid = self.mpc.listallinfo(uri)[0]
        except (mpd.CommandError, IndexError):
            self._sid = {}

        # setup sub lists
        cp_list = [('item', k, self._cp.get(k.lower()) or '') for k in self._song_key_list]
        siq_list = [('item', k, self._siq.get(k.lower()) or '') for k in self._song_key_list]
        sid_list = [('item', k, self._sid.get(k.lower()) or '') for k in self._song_key_list]
        stats_list = [('item', k, self.stats.get(k.lower()) or '') for k in self._stats_key_list]

        # convert list (multi-tags)  to str
        for l in (cp_list, siq_list, sid_list):
            for i in range(6):
                l[i] = (l[i][0], l[i][1], isinstance(l[i][2], str) and l[i][2] or ', '.join(l[i][2]))

        # format time
        for l in (cp_list, siq_list, sid_list):
            l[6] = (l[6][0], l[6][1], self._format_time(l[6][2]))
        for i in range(3, 6):
            stats_list[i] = (stats_list[i][0], stats_list[i][1], self._format_time(stats_list[i][2]))
        stats_list[6] = (stats_list[6][0], stats_list[6][1], time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(stats_list[6][2]))))

        # merge into main list
        self._options[2:10] = cp_list
        self._options[13:21] = siq_list
        self._options[24:32] = sid_list
        self._options[35:42] = stats_list

        # set up options display
        self._options_d = self._options[:]
        # breakup file paths
        for k in (31, 20, 9):
            self._options_d[k:k+1] = [('item', '', '/' + i) for i in self._options[k][2].split('/')]
            self._options_d[k] = ('item', 'File', self._options_d[k][2][1:])

        self.num = len(self._options_d)

    def uwin(self):
        self.win.erase()
        for i in range(self.beg, min(self.beg + self.height, self.num)):
            line = self._options_d[i]
            if line[0] == 'group':
                self.win.insstr(i - self.beg, 6, line[1], curses.A_BOLD)
            elif line[0] == 'hline':
                self.win.attron(curses.A_BOLD)
                self.win.hline(i - self.beg, 3, '-', self.width - 6)
                self.win.attroff(curses.A_BOLD)
            elif line[0] == 'item':
                self.win.insstr(i - self.beg, 0, line[1].rjust(20) + ' : ' + line[2])
            elif line[0] == 'blank':
                pass
        self.win.noutrefresh()

    def rdis(self):
        self._block_rdis()

class NCMPY_ARTIST_ALBUM(NCMPY_MOD, NCMPY_SCROLL):
    '''List artists/albums in database.'''

    def __init__(self, win, main):
        NCMPY_MOD.__init__(self, win, main)
        NCMPY_SCROLL.__init__(self)

        # current displayed dir
        self._type = 'artist'
        self._artist = None
        self._album = None
        self._view = self._build_view()

    def _build_view(self):
        '''Build view using self._type, self._artist and self._album.
        
        A view is rebuilt when self._type changes.'''

        if self._type == 'artist':
            view = self.mpc.list('artist')
        elif self._type == 'album':
            view = self._artist and self.mpc.list('album', self._artist) or []
        elif self._type == 'song':
            view = self._album and self.mpc.find('album', self._album) or []

        self.num = len(view)
        self.beg = 0
        self.sel = 0
        return view

    def round_one(self, c):
        if c == ord('j'):
            self.one_line_down()
        elif c == ord('k'):
            self.one_line_up()
        elif c == ord('f'):
            self.one_page_down()
        elif c == ord('b'):
            self.one_page_up()
        elif c == ord('H'):
            self.to_top()
        elif c == ord('M'):
            self.to_middle()
        elif c == ord('L'):
            self.to_bottom()
        elif c == ord('g'):
            self.to_begin()
        elif c == ord('G'):
            self.to_end()
        elif c == ord('\''):
            if self._type == 'artist':
                pass
            elif self._type == 'album':
                self._type = 'artist'
                self._view = self._build_view()
                for i in range(len(self._view)):
                    if self._view[i] == self._artist:
                        self.locate(i)
                        break
            elif self._type == 'song':
                self._type = 'album'
                self._view = self._build_view()
                for i in range(len(self._view)):
                    if self._view[i] == self._album:
                        self.locate(i)
                        break
        elif c == ord('"'):
            self._type = 'artist'
            self._view = self._build_view()
        elif c == ord('\n'):
            item = self._view[self.sel]
            if self._type == 'artist':
                self._artist = item
                self._type = 'album'
                self._view = self._build_view()
            elif self._type == 'album':
                self._album = item
                self._type = 'song'
                self._view = self._build_view()
            elif self._type == 'song':
                uri = item['file']
                songs = self.mpc.playlistfind('file', uri)
                if songs:
                    self.mpc.playid(songs[0]['id'])
                else:
                    self.mpc.add(uri)
                    song = self.mpc.playlistfind('file', uri)[0]
                    self.mpc.playid(song['id'])
        elif c == ord('a'):
            item = self._view[self.sel]
            if self._type == 'artist':
                self.mpc.findadd('artist', item)
            elif self._type == 'album':
                self.mpc.findadd('album', item)
            elif self._type == 'song':
                self.mpc.add(item['file'])
        elif c in [ord('/'), ord('?'), ord('n'), ord('N')]:
            self._search('Artist-Album', c)
        elif c == ord(';'):
            # tell QUEUE we want to locate a song
            if self._type == 'song':
                item = self._view[self.sel]
                self.board['locate'] = item.get('file')
            else:
                self.board['msg'] = 'No song selected'

    def round_two(self):
        if self.board.has_key('Database Updated.'):
            self._type = 'artist'
            self._view = self._build_view()

    def uwin(self):
        self.win.erase()
        for i in range(self.beg, min(self.beg + self.height, self.num)):
            item = self._view[i]

            if self._type in ['artist', 'album']:
                val = item
            elif self._type == 'song':
                val = self._get_tag('title', item) or os.path.basename(item.get('file'))

            if i == self.sel:
                self.win.attron(curses.A_REVERSE)
            if self._type == 'artist':
                self.win.attron(curses.color_pair(1) | curses.A_BOLD)
            elif self._type == 'album':
                self.win.attron(curses.color_pair(2) | curses.A_BOLD)
            self.win.hline(i - self.beg, 0, ' ', self.width)
            self.win.insstr(i - self.beg, 0, val)
            if self._type == 'artist':
                self.win.attroff(curses.color_pair(1) | curses.A_BOLD)
            elif self._type == 'album':
                self.win.attroff(curses.color_pair(2) | curses.A_BOLD)
            if i == self.sel:
                self.win.attroff(curses.A_REVERSE)
        self.win.noutrefresh()

    def rdis(self):
        self._block_rdis()

class NCMPY_SEARCH(NCMPY_MOD, NCMPY_SCROLL):
    '''Search in the database.'''

    def __init__(self, win, main):
        NCMPY_MOD.__init__(self, win, main)
        NCMPY_SCROLL.__init__(self)

        self._view = []

    def _build_view(self, kw):
        '''Build view using search keywords.'''
        
        try:
            name, value = kw.split(':', 1)
            view = self.mpc.find(name, value) or []
            if not view:
                self.board['msg'] = 'Nothing found :('
        except:
            view = []
            self.board['msg'] = 'Invalid Syntax >_< Syntax = <tag_name>:<tag_value>'

        self.num = len(view)
        self.beg = 0
        self.sel = 0
        return view

    def round_one(self, c):
        if c == ord('j'):
            self.one_line_down()
        elif c == ord('k'):
            self.one_line_up()
        elif c == ord('f'):
            self.one_page_down()
        elif c == ord('b'):
            self.one_page_up()
        elif c == ord('H'):
            self.to_top()
        elif c == ord('M'):
            self.to_middle()
        elif c == ord('L'):
            self.to_bottom()
        elif c == ord('g'):
            self.to_begin()
        elif c == ord('G'):
            self.to_end()
        elif c == ord('B'):
            self._view = self._build_view(self.main.e.getstr('Database Search'))
        elif c == ord('\n'):
            item = self._view[self.sel]
            uri = item['file']
            songs = self.mpc.playlistfind('file', uri)
            if songs:
                self.mpc.playid(songs[0]['id'])
            else:
                self.mpc.add(uri)
                song = self.mpc.playlistfind('file', uri)[0]
                self.mpc.playid(song['id'])
        elif c == ord('a'):
            item = self._view[self.sel]
            self.mpc.add(item['file'])
        elif c in [ord('/'), ord('?'), ord('n'), ord('N')]:
            self._search('Search', c)
        elif c == ord(';'):
            # tell QUEUE we want to locate a song
            if self.sel < self.num:
                item = self._view[self.sel]
                self.board['locate'] = item.get('file')
            else:
                self.board['msg'] = 'No song selected'

    def uwin(self):
        self.win.erase()
        for i in range(self.beg, min(self.beg + self.height, self.num)):
            item = self._view[i]

            val = self._get_tag('title', item) or os.path.basename(item.get('file'))

            if i == self.sel:
                self.win.attron(curses.A_REVERSE)
            self.win.hline(i - self.beg, 0, ' ', self.width)
            self.win.insstr(i - self.beg, 0, val)
            if i == self.sel:
                self.win.attroff(curses.A_REVERSE)
        self.win.noutrefresh()

    def rdis(self):
        self._block_rdis()

class NCMPY():
    '''Main controller.'''

    def _init_curses(self):
        self.stdscr = curses.initscr()
        curses.start_color()
        curses.use_default_colors()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        curses.init_pair(1, curses.COLOR_BLUE, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        self.stdscr.keypad(1)
        self.stdscr.leaveok(1)

    def _init_mpd(self, host, port):
        self.mpc = mpd.MPDClient()
        self.mpc.connect(host, port)

    def _init_conf(self):
        '''Initialize internal configurations.'''

        # main configuration
        self.height, self.width = self.stdscr.getmaxyx()
        self.tmodname = 'Database'
        self.tmodindex = 3
        self.tmodindexmax = 6
        self.loop = False
        self.idle = False
        self.seek = False
        self.sync = True
        self.elapsed = 0
        self.total = 0
        self.search = ''
        self.search_di = 0
        self.pending = []

        # no sync keys
        self.nsks = [
                ord('j'), ord('k'), ord('f'), ord('b'), 
                ord('H'), ord('M'), ord('L'), ord('g'), ord('G'), 
                curses.KEY_F7, curses.KEY_F2, curses.KEY_F3, curses.KEY_F4, 
                '/', '?', 'n', 'N', 
                -1
                ]
        # partial sync keys
        self.psks = [
                #curses.KEY_F10, curses.KEY_F9, curses.KEY_LEFT, curses.KEY_RIGHT,curses.KEY_NPAGE, curses.KEY_END, curses.KEY_DC
                curses.KEY_F10, curses.KEY_F9, curses.KEY_NPAGE, curses.KEY_END, curses.KEY_DC
                ]

        # user input
        self.c = None

    def _init_data(self):
        self.status = self.mpc.status()
        self.stats = self.mpc.stats()
        self.global_dir_index = 1
        self.currentsong = self.mpc.currentsong()

    def _init_board(self):
        self.board = {}

    def _init_mods(self):
        '''Initialize modules (mods).'''
        # Create curses windows BOBBINS
        self.m = NCMPY_MENU(self.stdscr.subwin(1, self.width, 0, 0), self)                    # menu
        self.t = NCMPY_TITLE(self.stdscr.subwin(1, self.width, 1, 0), self)                   # title
        self.p = NCMPY_PROGRESS(self.stdscr.subwin(1, self.width, self.height - 3, 0), self)  # progress
        self.s = NCMPY_STATUS(self.stdscr.subwin(2, self.width, self.height - 2, 0), self)    # status
        self.e = NCMPY_MESSAGE(self.stdscr.subwin(2, self.width, self.height - 2, 0), self)   # message
        self.h = NCMPY_HELP(curses.newwin(self.height - 5, self.width, 2, 0), self)           # help
        self.q = NCMPY_QUEUE(curses.newwin(self.height - 5, self.width, 2, 0), self)          # queue
        self.d = NCMPY_DATABASE(curses.newwin(self.height - 5, self.width, 2, 0), self)       # database
        self.l = NCMPY_LYRICS(curses.newwin(self.height - 5, self.width, 2, 0), self)         # lyrics
        self.a = NCMPY_ARTIST_ALBUM(curses.newwin(self.height - 5, self.width, 2, 0), self)   # artist-album
        self.r = NCMPY_SEARCH(curses.newwin(self.height - 5, self.width, 2, 0), self)         # search
        self.i = NCMPY_INFO(curses.newwin(self.height - 5, self.width, 2, 0), self)           # info

        # module dict
        self.mdict = {
                'Menu' : self.m, 
                'Title' : self.t, 
                'Progress' : self.p, 
                'Status' : self.s, 
                'Message' : self.e, 
                'Help' : self.h, 
                'Queue' : self.q, 
                'Database' : self.d, 
                'Lyrics' : self.l, 
                'Artist-Album' : self.a, 
                'Search' : self.r, 
                'Info' : self.i, 
                }
        # module list
        self.mlist = self.mdict.values()

        # bar module dict
        self.bmdict = {
                'Menu' : self.m, 
                'Title' : self.t, 
                'Progress' : self.p, 
                'Status' : self.s, 
                'Message' : self.e, 
                }
        # bar module list
        self.bmlist = self.bmdict.values()

    def __enter__(self):
        self._init_curses()
        self._init_mpd(conf['MPD_HOST'], conf['MPD_PORT'])
        self._init_conf()
        self._init_data()
        self._init_board()
        self._init_mods()

        # start lyrics daemon thread
        self.l.daemon = True
        self.l.start()

        # initial update
        self.process(fd='init')

        return self

    def __exit__(self, type, value, traceback):
        curses.endwin()

    def udata(self):
        # update main data
        self.status = self.mpc.status()
        self.stats = self.mpc.stats()
        self.currentsong = self.mpc.currentsong()

        # update mods data
        for mod in self.mlist:
            mod.udata()

    def round_one(self, c):
        # seeking
        #if c in (curses.KEY_LEFT, curses.KEY_RIGHT, curses.KEY_F9, curses.KEY_F10, curses.KEY_NPAGE, curses.KEY_END, curses.KEY_DC):
        if c in (curses.KEY_F9, curses.KEY_F10, curses.KEY_NPAGE, curses.KEY_END, curses.KEY_DC):
            if self.status['state'] in ['play', 'pause']:
                if not self.seek:
                    self.seek = True
                    self.elapsed, self.total = [int(i) for i in self.status['time'].split(':')]
                if c == curses.KEY_DC:
                    self.elapsed = max(self.elapsed - 1, 0)
                elif c == curses.KEY_NPAGE:
                    self.elapsed = min(self.elapsed + 1, self.total)
                #elif c == curses.KEY_F9:
                #    self.elapsed = max(self.elapsed - max(self.total / 100, 1), 0)
                #elif c == curses.KEY_F10:
                #    self.elapsed = min(self.elapsed + max(self.total / 100, 1), self.total)
                self.status['time'] = '{bib}:{bob}'.format(bib=self.elapsed, bob=self.total)
        else:
            if self.seek:
                self.status['time'] = '{bib}:{bob}'.format(bib=self.elapsed, bob=self.total)
                if self.status['state'] in ['play', 'pause']:
                    self.mpc.seekid(self.status['songid'], self.elapsed)
                self.seek = False

        # volume control
        if c == ord('-'):
            self.mpc.setvol(20)
            new_vol = max(int(self.status['volume']) - 1, 0)
            self.mpc.setvol(new_vol)
            self.status['volume'] = str(new_vol)
        elif c == ord('='):
            new_vol = min(int(self.status['volume']) + 1, 100)
            self.mpc.setvol(new_vol)
            self.status['volume'] = str(new_vol)

        # playback
        elif c == curses.KEY_HOME:
            self.mpc.pause()
        elif c == ord('s'):
            self.mpc.stop()
        elif c == curses.KEY_IC:
            self.mpc.previous()
        elif c == curses.KEY_PPAGE:
            self.mpc.next()

        # marks
        elif c == ord('u'):
            self.mpc.consume(1 - int(self.status['consume']))
            self.status['consume'] = 1 - int(self.status['consume'])
        elif c == ord('i'):
            self.mpc.random(1 - int(self.status['random']))
            self.status['random'] = 1 - int(self.status['random'])
        elif c == ord('o'):
            self.mpc.repeat(1 - int(self.status['repeat']))
            self.status['repeat'] = 1 - int(self.status['repeat'])
        elif c == ord('p'):
            self.mpc.single(1 - int(self.status['single']))
            self.status['single'] = 1 - int(self.status['single'])

        # playlist save/load
        elif c == ord('S'):
            name = self.e.getstr('Save')
            try:
                self.mpc.save(name)
            except mpd.CommandError as e:
                self.board['msg'] = str(e).rsplit('} ')[1]
            else:
                self.board['msg'] = 'Playlist {bib} saved'.format(bib=name)
                self.board['main-playlist'] = 'saved'
        elif c == ord('O'):
            name = self.e.getstr('Load')
            try:
                self.mpc.load(name)
            except mpd.CommandError as e:
                self.board['msg'] = str(e).rsplit('} ')[1]
            else:
                self.board['msg'] = 'Playlist {bib} loaded'.format(bib=name)

        # basic search
        elif c in [ord('/'), ord('?')]:
            search = self.e.getstr('Find')
            if search:
                self.search = search
                if c == ord('/'):
                    self.search_di = 1
                elif c == ord('?'):
                    self.search_di = -1
        #directory direct entry
        elif c == ord('0'):
            direcsearch = self.e.getstr('Directory')
            if direcsearch != '':
            	directory_jump_uri = self.d.find_directory_from_index(direcsearch)
            	self.d._dir = directory_jump_uri
            	self.d._view = self.d._build_view()
            	self.tmodname = 'Database'
            	self.tmodindex = 3

        # send to tmod
        self.mdict[self.tmodname].round_one(c)

        # other mods do round_one with no input char
        for modname in self.mdict:
            if modname != self.tmodname:
                self.mdict[modname].round_one(-1)

        # window switch
        # Must be placed AFTER keyevent is dispatched to tmod, 
        # since it happens in OLD tmod. 
        #if c == curses.KEY_F12:
        if c == ord('\t'):
            self.tmodindex += 1
            if self.tmodindex > self.tmodindexmax:
                 self.tmodindex = 1
            if self.tmodindex == 1:
                self.tmodname = 'Help'
            elif self.tmodindex == 2:
                self.q.locate(self.q.cur)
                self.tmodname = 'Queue'
            elif self.tmodindex == 3:
                self.tmodname = 'Database'
            elif self.tmodindex == 4:
                self.tmodname = 'Lyrics'
            elif self.tmodindex == 5:
                self.tmodname = 'Artist-Album'
            elif self.tmodindex == 6:
                self.tmodname = 'Search'
 
        if c in (curses.KEY_F7, curses.KEY_F2, curses.KEY_F3, curses.KEY_F4, curses.KEY_F5, curses.KEY_F6):
            if c == curses.KEY_F7:
                self.tmodname = 'Help'
                self.tmodindex = 1
            elif c == curses.KEY_F2:
                self.tmodname = 'Queue'
                self.q.locate(self.q.cur)
                self.tmodindex = 2
            elif c == curses.KEY_F3:
                self.tmodname = 'Database'
                self.tmodindex = 3
            elif c == curses.KEY_F4:
                self.tmodname = 'Lyrics'
                self.tmodindex = 4
            elif c == curses.KEY_F5:
                self.tmodname = 'Artist-Album'
                self.tmodindex = 5
            elif c == curses.KEY_F6:
                self.tmodname = 'Search'
                self.tmodindex = 6
        elif c == ord('h'):
            if self.tmodname != 'Info':
                self.board['prevtmodname'] = self.tmodname
                self.tmodname = 'Info'

    def round_two(self):
        if self.board.has_key('path'):
            self.tmodname = 'Database'

        if self.board.has_key('locate'):
            self.tmodname = 'Queue'

        if self.board.has_key('i_back'):
            self.tmodname = self.board['i_back']

        for mod in self.mlist:
            mod.round_two()

    def uwin(self):
        if conf['ENABLE_OSD']:
            self.l.uwin()

        self.mdict[self.tmodname].uwin()

        for mod in self.bmlist:
            mod.uwin()

        curses.doupdate()

    def enter_idle(self):
        '''Enter idle state. Must be called outside idle state.
        
        No return value.'''

        '''self.mpc.send_idle()'''
        self.idle = True

    def leave_idle(self):
        '''Leave idle state. Must be called inside idle state.
        
        Return Value: Events received in idle state.'''

        self.mpc.send_noidle()
        self.idle = False

        try:
            return self.mpc.fetch_idle()
        except mpd.PendingCommandError:
            # return None if nothing received
            return None

    def try_enter_idle(self):
        if not self.idle:
            self.enter_idle()

    def try_leave_idle(self):
        if self.idle:
            return self.leave_idle()

    def process(self, fd):
        '''Process init/timeout/mpd/stdin events. Called in main loop.'''
        
        tmod = self.mdict[self.tmodname]
        self.allnsks, self.allpsks = copy.deepcopy(self.nsks), copy.deepcopy(self.psks)
        self.allnsks.extend(tmod.nsks)
        self.allpsks.extend(tmod.psks)

        lastc = self.c

        # get input
        if fd == 'stdin':
            self.c = c = self.stdscr.getch()
        else:
            self.c = c = -1

        # sync vs nosync
        if fd == 'timeout':
            if self.status['state'] == 'play':
                self.sync = True
            elif lastc in self.allnsks:
                self.sync = False
            else:
                self.sync = True
        elif fd == 'init' or fd == 'mpd':
            self.sync = True
        elif fd == 'stdin':
            if c == ord('q'):
                self.loop = False
                return
            elif self.status['state'] == 'play':
                self.sync = True
            elif c in self.allnsks or c in self.allpsks:
                self.sync = False
            else:
                self.sync = True

        self.board.clear()

        if self.sync:
            events = self.try_leave_idle()

            if events and 'database' in events:
                self.board['main-database'] = 'updated'

            if c not in self.allpsks and self.pending:
                self.mpc.command_list_ok_begin()
                for task in self.pending:
                    exec('self.mpc.' + task)
                self.mpc.command_list_end()
                self.pending = []

            self.udata()
        self.round_one(c)   # nsks/psks won't cause interaction with server
        self.round_two()    # nsks/psks won't cause interaction with server
        self.uwin()         # won't interact with server

        if fd == 'stdin':
            curses.flushinp()
        else:
            self.try_enter_idle()

    def rdis(self):
        '''Reset display.
        
        Called when SIGWINCH is caught.'''

        curses.endwin()
        self.stdscr.refresh()
        self.height, self.width = self.stdscr.getmaxyx()

        for mod in self.mlist:
            mod.rdis()

    def main_loop(self):
        '''Main loop.'''

        poll = select.poll()
        poll.register(self.mpc.fileno(), select.POLLIN)
        poll.register(0, select.POLLIN)

        # already in idle state since __enter__ calls try_enter_idle in the end.
        self.loop = True
        while self.loop:
            try:
                responses = poll.poll(200)
                if not responses:
                    self.process(fd='timeout')
                else:
                    for fd, event in responses:
                        if fd == self.mpc.fileno() and event & select.POLLIN:
                            self.process(fd='mpd')
                        elif fd == 0 and event & select.POLLIN:
                            self.process(fd='stdin')
            except select.error:
                # SIGWINCH will cause select.error,
                # so no explicit SIGWINCH signal handler is used,
                # and SIGWINCH before poll starts won't be handled

                # reset display
                self.rdis()
                # eat up KEY_RESIZE and update
                self.process(fd='stdin')

if __name__ == '__main__':
    try:
        locale.setlocale(locale.LC_ALL,'')

        read_conf()

        if not os.path.isdir(conf['LYRICS_DIR']):
            os.makedirs(conf['LYRICS_DIR'])

        with NCMPY() as ncmpy:
            ncmpy.main_loop()
    finally:
        curses.endwin()
