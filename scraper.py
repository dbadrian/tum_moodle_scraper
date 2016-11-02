#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: David Adrian
# david.adrian@tum.de

import errno
import os
import requests
import argparse
import getpass

from selenium import webdriver
from progressbar import ProgressBar
# from selenium.webdriver.support.ui import Select # for <SELECT> HTML form


def make_fs_string(raw_string):
    return "_".join(raw_string.split(" ")).lower()


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def tum_login(driver, user, password=""):
    driver.get("https://www.moodle.tum.de/login/index.php")
    a = driver.find_element_by_link_text('TUM LOGIN')
    a.click()

    # Fill the login form and submit it
    driver.find_element_by_id('j_username').send_keys(user)
    if password:
        driver.find_element_by_id('j_password').send_keys(password)
    else:
        driver.find_element_by_id('j_password').send_keys(getpass.getpass("Please enter your password:"))
    driver.find_element_by_id('Login').submit()
    return driver


def lmu_login():
    pass


def get_session(driver):
    session = requests.Session()
    cookies = driver.get_cookies()
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'])
    return session


def get_driver(driver_type):
    if driver_type == "phantomjs":
        # On Windows, use: webdriver.PhantomJS('C:\phantomjs-1.9.7-windows\phantomjs.exe')
        driver = webdriver.PhantomJS()
    elif driver_type == "chrome":
        driver = webdriver.Chrome()
    elif driver_type == "firefox":
        driver = webdriver.Firefox()

    return driver


def get_courses(driver, semester):
    courses = driver.find_elements_by_class_name('coc-course')
    course_list = []
    for course in courses:
        term = course.find_element_by_class_name("termdiv") \
                     .get_attribute('class').split(" ")[1].split("-")
        term = '-'.join(term[2:])
        # Easier for now to just filter by semester (if request),
        # than dealing with hidden-classes
        if term == semester or semester == "all":
            a = course.find_element_by_xpath(".//h3/a")
            title = "_".join(a.get_attribute('title').split(" ")).lower()
            course_list.append((term, title, a.get_attribute('href')))

    return course_list


def download_files(session, fn_base, files, force):
    # Download Files
    for file in files:
        # Create Folder if it doesn't exist yet
        path = os.path.join(fn_base, file[0], file[1])
        mkdir_p(path)

        # Download File
        # NOTE the stream=True parameter
        # NOTE add the "&redirect=1", to deal with some odd balls
        r = session.get(file[2] + "&redirect=1", stream=True)
        fs = int(r.headers['Content-Length'])
        name = r.headers["Content-Disposition"].split('\"')[-2].decode('utf-8')
        fn = os.path.join(path, name)
        if not force and os.path.isfile(fn) and os.stat(fn).st_size == fs:
            print "   :: File already exists. Skipping", file[1], name, "!"
        else:
            print "   :: Downloading:", file[1], name
            with open(fn, 'wb') as f:
                pbar = ProgressBar(maxval=fs).start()
                for idx, chunk in enumerate(r.iter_content(chunk_size=1024)):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
                        pbar.update(idx * 1024)
                pbar.finish()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fn_out', '-o', type=str, default='',
                        help='Output folder',
                        required=True)
    parser.add_argument('--user', '-u', type=str, default='',
                        help='Shibboleth User',
                        required=True)
    parser.add_argument('--pw', '-p', type=str, default='',
                        help='(OPTIONAL DEV) Shibboleth Password',
                        required=False)
    parser.add_argument('--semester', '-s', type=str, default='all',
                        help='Filter courses by semester',
                        required=False)
    parser.add_argument('--driver', '-d', type=str, default='phantomjs',
                        help='Phantomjs, Chrome, Firefox supported',
                        required=False)
    parser.add_argument('--force', '-f', dest='force', action='store_true',
                        help='Force re-downloads every file',
                        required=False)
    args = parser.parse_args()


# Obtain Driver
print " :: Obtaining Driver"
driver = get_driver(args.driver.lower())

# We are now on the course pages
print " :: Login User:", args.user
tum_login(driver, args.user, args.pw)

# print " :: Setting Semester to ", args.semester
# set_semester(args.semester)

# Get all courses and filter by semester/all
print "\n :: Getting Courses of", args.semester
courses = get_courses(driver, args.semester)
print "   :: Found:", len(courses), "courses!"

print "\n :: Collecting File Information"
# First get all special cases pre-processed
## TODO: Should be recursive just to make sure!
folder_queue = []
section_queue = []
for course in courses:
    print "   ::", course[0], course[1]
    driver.get(course[2])

    # 2. Get folders
    try:
        # TODO: Timeout problems?
        folders = driver.find_elements_by_class_name("modtype_folder")
        for folder in folders:
            folder_href = folder.find_element_by_xpath(".//a").get_attribute('href')
            folder_name = make_fs_string(folder.find_element_by_class_name("instancename").text)
            folder_queue.append(((course[0], os.path.join(course[1], folder_name), folder_href)))
    except:
        print "   :: Folder Search Failed!!!"

    # 3. Deal with sections (similar to folder)
    try:
        # 2. Recurse through folder
        # TODO: Timeout problems?
        folders = driver.find_elements_by_class_name("section-summary")
        for folder in folders:
            link_el = folder.find_element_by_xpath(".//a")
            folder_href = link_el.get_attribute('href')
            folder_name = make_fs_string(link_el.text)
            section_queue.append(((course[0], os.path.join(course[1], folder_name), folder_href)))
    except:
        print "   :: Folder Search Failed!!!"

# Now treat everything as page and look for files
parsed_files = []
pages = courses + folder_queue + section_queue
# pages = folder_queue
for page in pages:
    # 1. Find single files
    driver.get(page[2])
    try:
        files = driver.find_elements_by_class_name("modtype_resource") + driver.find_elements_by_class_name("fp-filename-icon")
        for file in files:
            try:
                file_href = file.find_element_by_xpath(".//a").get_attribute('href')
                parsed_files.append((page[0], page[1], file_href))
            except:
                # wasnt a file, only icon
                pass
    except:
        print "   :: No Files Found!"

# Download files if they don't exist.
print "\n :: Collected", len(parsed_files), "files"
print " :: Downloading files (please wait)"
download_files(get_session(driver), args.fn_out, parsed_files, args.force)