import time
import shutil
from datetime import datetime
from pathlib import Path
try:
    import ashjdfioastkjl
    from rich.table import Table, Column
    from rich.progress import Task, _TrackThread, Progress, BarColumn, TextColumn, TimeElapsedColumn, \
        TimeRemainingColumn, SpinnerColumn
    from rich.panel import Panel
    from rich.style import StyleType
    from rich.text import Text, TextType
    from rich.console import Console

    RICH = True
except ModuleNotFoundError:
    print('rich not imported')

    RICH = False
    console_width = 78  # preferably an even number (but not required)


    class Progress():
        def __init__(self):
            print('*' * 80)
            print('rich not imported, using simpler version instead, console width =', console_width)

from typing import Iterable, Optional, Sequence, TypeVar, Union, NewType, Any
from collections.abc import Sized

TaskID = NewType("TaskID", int)
ProgressType = TypeVar("ProgressType")





class Tracking_Pane(Progress):
    # TODO add a notepad.txt file & let ppl add anything to it
    '''
    WARNINGS:
        try and make your titles less than 12 chars long for better formatting :)
        csv stats must always be the same # TODO: add a check to make sure stats are the same
        each time .track is called it MUST use a new/diff task param NOT the same

        PARAMS:

        - dir_path: directory location to save files

        - mode: str = "trn_seg" or "im_to_samp"

        - stats_to_track:
                          dict{ task : [stat_title,
                                        stat_title,
                                        [stat_title, custom_indent_size ],     NOTE: default indent = 12
                                        [stat_title, track_stat_inLoop_flag ], NOTE: def method is to use .add_stat(...)
                                        etc...],
                                etc...}

    '''
    def __init__(self, dir_path, mode=None, stats_to_track=None):

        # mode specific inits
        if mode==None and stats_to_track != None:
            pass
        elif mode not in ['trn_seg', 'im_to_samp', 'inf']:
            raise NotImplementedError(f'please select a valid mode (ur choices = ["trn_seg", "im_to_samp", "inf"])')

        elif mode == 'trn_seg':
            stats_to_track = {'epoch' : ['save_check',
                                         'iou',
                                         'val loss',
                                         'trn loss',
                                         'precision',
                                         'recall',
                                         'fscore'],
                              'batch' : ['dataset',
                                         ['epoch', True], # flag denoting this stat is tracked by tracker.track(...)
                                                                                  # instead of tracker.add_stat(...)
                                         'loss',
                                         'gpu_perc',
                                         'gpu_RAM',
                                         'device',
                                         ['samples', 20], # specific indent size
                                         'lr']}

        elif mode == 'im_to_samp':
            stats_to_track = {'csv' : ['gpkg',
                                       'img',
                                       'size']}

        elif mode == 'inf':
            raise NotImplementedError('TODO: if this is not MATT looking at this ...very sorry')
        else:
            raise NotImplementedError('sorry, please enter a valid mode, ')



        # general inits
        self.dir = dir_path
        self.mode = mode # todo: I can prob remove this now
        self.start_time = {}

        # init stat dictionaries
        self.stats = {}
        self.stat_titles = {}
        self.stat_indents = {}
        self.track_stat_inLoop = []
        for task in stats_to_track:
            self.stats[task] = {}
            self.stat_titles[task] = []
            self.stat_indents[task] = []

            # add column titles (just the basics)
            self.stat_titles[task] += stats_to_track[task]
            self.stat_indents[task] += [12] * len(stats_to_track[task])

            # check for specified params in each column title
            for c in range(len(self.stat_titles[task])):
                if isinstance(self.stat_titles[task][c], list):
                    for item in self.stat_titles[task][c][1:]:
                        if isinstance(item, bool):  # whether or not to track stats used in for loops tracker.track(...)
                            self.track_stat_inLoop.append([task, self.stat_titles[task][c][0]])
                        elif isinstance(item, int):   # indent sizes
                            self.stat_indents[task][c] = item
                    # self.stat_titles[task][c] = self.stat_titles[task][c][1]
                    self.stat_titles[task][c] = self.stat_titles[task][c][0] # set the stat column title (str)

            # insert the task itself into the column titles
            self.stat_titles[task].insert(0, task)
            self.stat_indents[task].insert(0, 12)

        # create files
        with open(self.dir / 'live.txt', 'a') as file:
            file.write('               curr     total    |     time elapsed      est. time remain    est. total time\n\n')

        for num, task in enumerate(stats_to_track):
            with open(self.dir / f'per_{task}.csv', 'a') as file:

                titles = ''
                for t, tit in enumerate(self.stat_titles[task]):
                    titles += f"{tit},{' ' * (self.stat_indents[task][t]  - len(tit))}"
                titles += 'time elapsed,     est. time remain,   est. total time\n'
                file.writelines((titles, '\n'))




    def track(self, seq, task):
        # todo: add rich & tdqm track opts
        for num, value in enumerate(seq): # TODO!!! should we have 0/39 OR 1/40 ???
            # self.note(f'flag!!\t{num}\t{task}\n{self.stats}\n\n' * 25)

            # timers
            if num == 0: # reset timer & avoid div0 errors
                print('-'*40)
                print('\t\t', 'STARTING\t', task)
                print('-'*40)

                self.start_time[task] = time.time()
                time_curr = 0
                time_total = 0
                time_remain = 0
            else:
                time_curr = time.time() - self.start_time[task]
                time_total = time_curr / num * (len(seq)-1)
                time_remain = (time_total - time_curr)

                # add to file
                self.add_stat(task, f'{num-1} / {len(seq)-1}', task=task) # add curr loop
                row = self.make_csv_row(task,
                                        time_curr,
                                        time_remain,
                                        time_total)
                with open(self.dir / f'per_{task}.csv', 'a') as file:
                    file.write(row)

                self.__clear_stats(task)

            # region add to live.txt file
            with open(self.dir / 'live.txt', 'r') as file:
                data = file.readlines()

            EXISTS = False
            for d in range(len(data)):

                if data[d][:len(task)] == task:
                    index = d
                    EXISTS = True
                    break

            if not EXISTS:
                index = len(data)
                data.append('')

            time_remain = f"{(time_remain / 60):.0f}m " \
                          f"{(time_remain % 60):.0f}s"
            time_curr = f"{(time_curr / 60):.0f}m " \
                        f"{(time_curr % 60):.0f}s"
            time_total = f"{(time_total / 60):.0f}m " \
                         f"{(time_total % 60):.0f}s"
            data[index] = f"{task}{' '*(12-len(task))}:   " \
                          f"{num}{' '*(4-len(str(num)))} /   " \
                          f"{len(seq)}{' '*(4-len(str(len(seq))))}           " \
                          f"{time_curr}{' '*(12-len(time_curr))}         " \
                          f"{time_remain}{' '*(12-len(time_remain))}        " \
                          f"{time_total}{' '*(12-len(time_total))}        " \
                          f"\n"

            data = data[:index+1] # reset lower other vals for next time
            # TODO: just remove the curr value? do we need to delete all the vals - or try putting the '-> ' arrow at the start again

            # print(data[0], data[index])
            # self.print(data[0], data[index])

            with open(self.dir / 'live.txt', 'w') as file:
                file.writelines(data)       # todo: except possible file writing errs!!!

            # endregion

            for stat_info in self.track_stat_inLoop:
                if task == stat_info[1]: # 1=name of stat
                    self.add_stat(stat_info[1], f'{num} / {len(seq)-1}', task=stat_info[0]) # 0=task that tracks the stat

            yield value
    # TODO: documentation!
    def make_csv_row(self, task, time_curr, time_remain, time_total, row=''):
                                                                                                # TODO! it curr doesnt save the stats of the last in seq!!!
        # region add stats to row
        for t, tit in enumerate(self.stat_titles[task]) :
            try:
                stat = self.stats[task][tit]
                try:
                    stat = f"{stat:.5f}" # todo: allow formating? f'{}'.format(...)
                except (ValueError, TypeError):
                    stat = f"{stat}"                # self.stat_title[task][col] => indent
                stat = stat.replace(',', '')
                row += f"{stat},{' ' * (self.stat_indents[task][t] - len(stat))}"            # TODO: for batch & epochs, add in the total! (ex = if col=='total' len(seq))
            except KeyError: # if a stat has not been added for this row
                row += ',' + ' ' * self.stat_indents[task][t]                                # TODO: fix if they are too big, add space in column
        # endregion

        # region timers
        time_remain = f"{(time_remain / 60):.0f}m " \
                      f"{(time_remain % 60):.0f}s"
        time_curr = f"{(time_curr / 60):.0f}m " \
                    f"{(time_curr % 60):.0f}s"
        time_total = f"{(time_total / 60):.0f}m " \
                     f"{(time_total % 60):.0f}s"
        row += f"{time_curr},{' ' * (18 - len(time_curr))}" \
                f"{time_remain},{' ' * (18 - len(time_remain))}" \
                f"{time_total},{' ' * (18 - len(time_total))}\n"
        # endregion

        return row

    def notify_end(self, task):
        print('-'*36)
        print('\t\t', task, '\tENDED')
        print('-'*36)

        # region timers
        time_curr = time.time() - self.start_time[task]
        time_total = time_curr
        time_remain = 0
        # endregion

        # region add to file
        # todo: get previous num in seq, +1, add back to stats OR get self.len(seq) ?
        # with open(self.dir / 'per_batch.csv', 'r') as file:
        #     #         last_line = file.readlines()[-1][:20].replace(' ', ',').split(',')
        row = self.make_csv_row(task,
                                time_curr,
                                time_remain,
                                time_total)
        with open(self.dir / f'per_{task}.csv', 'a') as file:
            file.write(row)

        self.__clear_stats(task)
        # endregion

    def add_stat(self, key, stat, task='epoch'):
        self.stats[task][key] = stat
    # TODO: when add_stat() check that these are part of the dict
    def add_stats(self, stats, task='epoch'): # todo: makes sure its a dict
        for key in stats:
            self.stats[task][key] = stats[key] # todo: can this be 'vectoried' or atleast not looped?

    def __clear_stats(self, task):
        save_me = {}
        for stat_info in self.track_stat_inLoop:
            if stat_info[1] in self.stats[task]: # 1=name of stat
                save_me[stat_info[1]] = self.stats[task][stat_info[1]]
        self.stats[task] = save_me

    def note(self, line, end='\n'):
        # TODO: allow for printing things like epoch_num
        # TODO: allow more types other than just strings (with *arg), but what if *arg=['', []] then we need to go recursive! - look at
        with open(self.dir / 'notepad.txt', 'a') as file:
            file.write(f'{line}')
            file.write(end)


if __name__ == '__main__':
    batches = [[0, 1, 2, 3, 55],
               [0, 1, 2, 3],
               [0, 1, 2, 3, 55, 33]]
    tracker = Tracking_Pane('C:/Users/muzwe/Documents/GitHub/geo-deep-learning - MATT/MATTS',
                            mode='trn_seg',
                            stats_to_track={'epoch' : ['save_check']})
    for i in tracker.track(range(6), 'epoch'):#task_id=0):
        print('epoch', i)
        tracker.add_stat('lol', i)

        for j in tracker.track(batches[i % 3], 'trn batch'):#task_id=1):
            print('\ttrn batch :', j)
            time.sleep(1)
            for k in tracker.track(range(2), 'trn vis'):
                print('\t\ttrn vis :', k)
                time.sleep(1)

        for jj in tracker.track(batches[i % 3], 'val batch'):#task_id=1):
            print('\tval batch :', jj)
            time.sleep(1)
            for k in tracker.track(range(2), 'val vis'):
                print('\t\tval vis :', k)
                time.sleep(1)