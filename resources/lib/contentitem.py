#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
This module contains the classes MovieItem and EpisodeItem,
in addition to the parent class ContentItem
'''

import os
from fnmatch import fnmatch
from glob import glob
from bs4 import BeautifulSoup

import xbmc
import xbmcaddon

from utils import log_msg, get_items, save_items, append_item, clean

MANAGED_FOLDER = xbmcaddon.Addon().getSetting('managed_folder')

class ContentItem(object):
    '''
    this is a parent class for MovieItem and EpisodeItem,
    and defines required methods, and a few helper methods
    '''
    #?TODO: remove mediatype from init now that there are subclasses
    #TODO: create refresh method so you don't have to remove_from_staged then add_to_staged_file
    #TODO: make rename on add & metadata on stage optional in settings
    #TODO: save original_label, would be able to rename entire filename using metadata

    def __init__(self, path, title, mediatype):
        #TODO: add parent folder and optional year param
        #TODO: move create_metadata_item to new stage() method
        self.path = path.encode('utf-8')
        self.mediatype = mediatype.encode('utf-8')
        try:
            self.title = title.encode('utf-8')
        except UnicodeEncodeError:
            self.title = title.decode('utf-8').encode('utf-8')

    def __str__(self):
        return '[B]%s[/B] - [I]%s[/I]' % (self.title, self.path)

    def add_to_library(self):
        ''' defines required method for child classes -- adds its content to the library '''
        #TODO: add to library using json-rpc
        raise NotImplementedError('ContentItem.add_to_library() not implemented!')

    def remove_from_library(self):
        ''' defines required method for child classes -- removes its content from the library '''
        #TODO: remove from library using json-rpc
        raise NotImplementedError('ContentItem.remove_from_library() not implemented!')

    def remove_and_block(self):
        '''
         defines required method for child classes --
         removes its content from the library, deletes metadata, and adds to blocked list
         '''
        raise NotImplementedError('ContentItem.remove_and_block() not implemented!')

    def create_metadata_item(self):
        ''' defines required method for child classes -- adds relevent files to metadata folder '''
        raise NotImplementedError('ContentItem.create_metadata_item() not implemented!')

    def rename_using_metadata(self):
        ''' defines required method for child classes -- automatically rename using nfo file '''
        raise NotImplementedError('ContentItem.rename_using_metadata() not implemented!')

    def rename(self, name):
        ''' defines required method for child classes -- rename title and files '''
        raise NotImplementedError('ContentItem.rename(name) not implemented!')

    def add_to_managed_file(self):
        ''' adds object to managed file '''
        items = get_items('managed.pkl')
        items.append(self)
        save_items('managed.pkl', items)

    def add_to_staged_file(self):
        ''' adds object to staged file '''
        # TODO: create stage() method, and move the call to create_metadata_item there
        items = get_items('staged.pkl')
        items.append(self)
        save_items('staged.pkl', items)

    def remove_from_managed(self):
        ''' removes all items with the object's path from managed file '''
        managed = get_items('managed.pkl')
        for item in managed:
            if item.get_path() == self.path:
                managed.remove(item)
        save_items('managed.pkl', managed)

    def remove_from_staged(self):
        ''' removes all items with the object's path from staged file '''
        staged = get_items('staged.pkl')
        for item in staged:
            if item.get_path() == self.path:
                staged.remove(item)
        save_items('staged.pkl', staged)

    def get_title(self):
        return self.title

    def get_path(self):
        return self.path

    def get_mediatype(self):
        return self.mediatype

class MovieItem(ContentItem):
    '''
    keeps track of a movie item from a plugin,
    and manages its content in managed/staged files and folders
    '''
    #TODO: implement rename & rename_using_metadata

    def __init__(self, path, title, mediatype):
        super(MovieItem, self).__init__(path, title, mediatype)

    def add_to_library(self):
        # parse and fix file/dir names
        safe_title = clean(self.title)
        movie_dir = os.path.join(MANAGED_FOLDER, 'ManagedMovies', safe_title)
        filepath = os.path.join(movie_dir, safe_title + '.strm')
        # create directory for movie
        os.system('mkdir "%s"' % movie_dir)
        # add metadata (optional)
        metadata_dir = os.path.join(MANAGED_FOLDER, 'Metadata', 'Movies', safe_title)
        if os.path.isdir(metadata_dir):
            os.system('ln -s "%s/"* "%s"' % (metadata_dir, movie_dir))
            os.system('rm "%s/*.strm"' % movie_dir)
        # add stream file to movie_dir
        os.system('echo "%s" > "%s"' % (self.path, filepath))
        # add to managed file
        self.add_to_managed_file()
        self.remove_from_staged()

    def remove_from_library(self):
        safe_title = clean(self.title)
        movie_dir = os.path.join(MANAGED_FOLDER, 'ManagedMovies', safe_title)
        os.system('rm -r "%s"' % movie_dir)
        self.remove_from_managed()

    def remove_and_block(self):
        # add title to blocked
        append_item('blocked.pkl', {'type':'movie', 'label':self.title})
        # delete metadata items
        safe_title = clean(self.title)
        movie_dir = os.path.join(MANAGED_FOLDER, 'Metadata', 'Movies', safe_title)
        os.system('rm -r "%s"' % movie_dir)
        # remove from staged
        self.remove_from_staged()

    def create_metadata_item(self):
        safe_title = clean(self.title)
        movie_dir = os.path.join(MANAGED_FOLDER, 'Metadata', 'Movies', safe_title)
        filepath = os.path.join(movie_dir, safe_title+'.strm')
        os.system('mkdir "%s"' % movie_dir)
        os.system('echo "" > "%s"' % filepath)

class EpisodeItem(ContentItem):
    '''
    keeps track of a tvshow episode item from a plugin,
    and manages its content in managed/staged files and folders
    '''

    def __init__(self, path, title, mediatype, show_title):
        self.show_title = show_title.encode('utf-8')
        super(EpisodeItem, self).__init__(path, title, mediatype)

    def __str__(self):
        return '[B]%s[/B] - [I]%s[/I]' % (self.title, self.path)

    def add_to_library(self):
        #TODO: add a return value so Staged will know if episode wasn't added
        #       and can display a relevant notification
        # rename episode if metadata is available
        self.rename_using_metadata()
        # don't add episodes that don't have episode id in name
        safe_title = clean(self.title)
        if not (fnmatch(safe_title, '*[0-9]x[0-9]*')\
            or fnmatch(safe_title, '*[Ss][0-9]*[Ee][0-9]*')):
            return
        # check if tvshow folder already exists
        safe_showtitle = clean(self.show_title)
        metadata_dir = os.path.join(MANAGED_FOLDER, 'Metadata', 'TV', safe_showtitle)
        show_dir = os.path.join(MANAGED_FOLDER, 'ManagedTV', safe_showtitle)
        if not os.path.isdir(show_dir):
            # if not, create folder in ManagedTV
            os.system('mkdir "%s"' % show_dir)
            if os.path.isdir(metadata_dir):
                # link tvshow.nfo and artwork now, if metadata_dir exists
                files = os.listdir(metadata_dir)
                for fname in files:
                    if not (fnmatch(fname, '*[0-9]x[0-9]*') \
                        or fnmatch(fname, '*[Ss][0-9]*[Ee][0-9]*') \
                        or '.strm' in fname):
                        os.system('ln -s "{0}" "{1}"'.format(
                            os.path.join(metadata_dir, fname), os.path.join(show_dir, fname)))
        # create stream file
        filepath = os.path.join(show_dir, safe_title+'.strm')
        os.system('echo "{0}" > "{1}"'.format(self.path, filepath))
        # link metadata for episode if it exists
        if os.path.isdir(metadata_dir):
            nfo_path = os.path.join(metadata_dir, safe_title+'.nfo')
            if os.path.exists(nfo_path):
                os.system('ln -s "{0}" "{1}"'.format(nfo_path, show_dir))
            thumb_path = os.path.join(metadata_dir, safe_title+'-thumb.jpg')
            if os.path.exists(thumb_path):
                os.system('ln -s "{0}" "{1}"'.format(thumb_path, show_dir))
        # remove from staged, add to managed
        self.add_to_managed_file()
        self.remove_from_staged()

    def remove_from_library(self):
        # delete stream, nfo & thumb
        safe_showtitle = clean(self.show_title)
        safe_title = clean(self.title)
        show_dir = os.path.join(MANAGED_FOLDER, 'ManagedTV', safe_showtitle)
        #os.remove(os.path.join(show_dir, safe_title))
        os.system('rm "%s"*' % os.path.join(show_dir, safe_title))
        # check if last stream file, and remove entire dir if so
        files = os.listdir(show_dir)
        remove_dir = True
        for fname in files:
            if '.strm' in fname:
                remove_dir = False
                break
        if remove_dir:
            os.system('rm -r "%s"' % show_dir)
        # remove from managed list
        self.remove_from_managed()

    def remove_and_block(self):
        # add show title to blocked
        append_item('blocked.pkl', {'type':'episode', 'label':self.title.replace('-0x0', '')})
        # delete metadata items
        safe_showtitle = clean(self.show_title)
        safe_title = clean(self.title)
        title_path = os.path.join(MANAGED_FOLDER, 'Metadata', 'TV', safe_showtitle, safe_title)
        os.system('rm "%s"*' % title_path)
        # remove from staged
        self.remove_from_staged()

    def create_metadata_item(self):
        #TODO: automatically call this when staging
        #TODO: actually create basic nfo file with name and episode number, and thumb if possible
        #?TODO: could probably just rename based on existing strm file instead of nfo file
        #   (shouldn't make a difference though)
        # create show_dir in Metadata/TV if it doesn't already exist
        safe_showtitle = clean(self.show_title)
        show_dir = os.path.join(MANAGED_FOLDER, 'Metadata', 'TV', safe_showtitle)
        if not os.path.exists(show_dir):
            os.system('mkdir "%s"' % show_dir)
        # check for existing stream file
        safe_title = clean(self.title)
        strm_path = os.path.join(show_dir, safe_title+'.strm')
        # only create metadata item if it doesn't already exist (by checking for stream title)
        if not os.path.exists(strm_path):
            # rename file if old nfo file has episode id
            old_renamed = glob(os.path.join(show_dir, '*[0-9]x[0-9]* - {0}.nfo'.format(safe_title)))
            if old_renamed:
                # prepend title with epid if so
                epid = old_renamed[0].split('/')[-1].replace(safe_title+'.nfo', '')
                new_title = epid + self.title
            elif not (fnmatch(safe_title, '*[0-9]x[0-9]*') or \
                fnmatch(safe_title, '*[Ss][0-9]*[Ee][0-9]*')):
                # otherwise, append -0x0 if title doesn't already have episode id
                new_title = self.title + '-0x0'
            else:
                new_title = self.title
            # create a blank file so media managers can recognize it and create nfo file
            filepath = os.path.join(show_dir, clean(new_title)+'.strm')
            os.system('echo "" > "%s"' % filepath)
            # refresh item in staged file if name changed
            if new_title != self.title:
                self.title = new_title
                self.remove_from_staged()
                self.add_to_staged_file()

    def rename(self, name):
        # rename files if they exist
        safe_showtitle = clean(self.show_title)
        safe_title = clean(self.title)
        metadata_dir = os.path.join(MANAGED_FOLDER, 'Metadata', 'TV', safe_showtitle)
        if os.path.isdir(metadata_dir):
            # define "title paths" (paths without extensions)
            title_path = os.path.join(metadata_dir, safe_title)
            new_title_path = os.path.join(metadata_dir, clean(name))
            # rename stream placeholder, nfo file, and thumb
            os.system('mv "%s"*.strm "%s.strm"' % (title_path, new_title_path))
            os.system('mv "%s"*.nfo "%s.nfo"' % (title_path, new_title_path))
            os.system('mv "%s"*-thumb.jpg "%s-thumb.jpg"' % (title_path, new_title_path))
        # rename property and refresh in staged file
        self.title = name
        self.remove_from_staged()
        self.add_to_staged_file()

    def rename_using_metadata(self):
        #?TODO: rename show_title too
        safe_showtitle = clean(self.show_title)
        safe_title = clean(self.title)
        metadata_dir = os.path.join(MANAGED_FOLDER, 'Metadata', 'TV', safe_showtitle)
        nfo_path = os.path.join(metadata_dir, safe_title+'.nfo')
        log_msg('nfo_path: %s' % nfo_path)
        # only rename if nfo file exists
        if os.path.exists(nfo_path):
            # open nfo file and get xml soup
            with open(nfo_path) as fp:
                soup = BeautifulSoup(fp)
            # check for season & episode tags
            season = int(soup.find('season').get_text())
            episode = int(soup.find('episode').get_text())
            # format into episode id
            epid = '{0:02}x{1:02} - '.format(season, episode)
            log_msg('epid: %s' % epid, xbmc.LOGNOTICE)
            # only rename if epid not already in name (otherwise it would get duplicated)
            if epid not in safe_title:
                new_title = epid + safe_title.replace('-0x0', '')
                self.rename(new_title)
            elif '-0x0' in safe_title:
                new_title = safe_title.replace('-0x0', '')
                self.rename(new_title)

    def get_show_title(self):
        return self.show_title