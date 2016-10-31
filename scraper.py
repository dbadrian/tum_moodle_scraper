from selenium import webdriver
import errno
import os
import requests
import argparse
import getpass
import menu
import logging
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


def get_driver(driver_type):
    if driver_type == "phantomjs":
        # On Windows, use: webdriver.PhantomJS('C:\phantomjs-1.9.7-windows\phantomjs.exe')
        driver = webdriver.PhantomJS()
    elif driver_type == "chrome":
        driver = webdriver.Chrome()
    elif driver_type == "firefox":
        driver = webdriver.Firefox()

    return driver


# But actually only looking at non-hidden is a pain, so i just filter the list
# def set_semester(semester):
#     if semester == "all":
#         # Switch on to view all courses
#         driver.find_element_by_xpath("//select[@id='coc-filterterm']/option[@value='all']").click()
#         return True
#     else:
#         try:
#             el = driver.find_element_by_xpath("//select[@id='coc-filterterm']/option[@value=\'" + semester + "\']").click()
#         except:
#             print "ERROR: Semester", semester, "does not exist!"


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


def download_file(session, path, url):
    # NOTE the stream=True parameter
    r = session.get(url, stream=True)
    total_size = int(r.headers['Content-Length'])
    fn = os.path.join(path, r.url.split('/')[-1])
    with open(fn, 'wb') as f:
        pbar = ProgressBar(maxval=total_size).start()
        for idx, chunk in enumerate(r.iter_content(chunk_size=1024)):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
                pbar.update(idx * 1024)
        pbar.finish()


def download_files(session, fn_base, files):
    # Download Files
    for file in files:
        print "Processing: ", file[1], file[2]

        # Create Folder if it doesn't exist yet
        path = os.path.join(fn_base, file[0], file[1])
        mkdir_p(path)

        # TODO CHECK IF FILE EXISTS ON FS BEFORE DOWNLOADING

        # Download File
        download_file(session, path, file[3])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fn_out', '-o', type=str, default='',
                        help='Output folder',
                        required=True)
    parser.add_argument('--user', '-u', type=str, default='',
                        help='Shibboleth User',
                        required=True)
    parser.add_argument('--pw', '-p', type=str, default='',
                        help='Dev param, password will be visible',
                        required=False)
    parser.add_argument('--semester', '-s', type=str, default='all',
                        required=False)
    parser.add_argument('--driver', '-d', type=str, default='phantomjs',
                        required=False)
    args = parser.parse_args()


# Obtain Driver
print " :: Obtaining Driver"
driver = get_driver(args.driver)

# We are now on the course pages
print " :: Login"
tum_login(driver, args.user, args.pw)

# print " :: Setting Semester to ", args.semester
# set_semester(args.semester)

# Get all courses and filter by semester/all
print " :: Getting Courses of", args.semester
courses = get_courses(driver, args.semester)
# print courses

print " :: Collecting File Information"

# now process all the courses

folder_queue = []
section_queue = []

for course in courses:
    print course[0], course[1]
    driver.get(course[2])

    try:
        # 2. Recurse through folder
        # TODO: Timeout problems?
        folders = driver.find_elements_by_class_name("modtype_folder")
        for folder in folders:
            folder_href = folder.find_element_by_xpath(".//a").get_attribute('href')
            folder_name = make_fs_string(file.find_element_by_class_name("instancename").text)
            folder_queue.append(((course[0], os.path.join(course[1], folder_name), folder_href)))
    except:
        print " :: :: Folder Search Faield!!!"

    # 3. Deal with sections (similar to folder)
    # try:
    #     # 2. Recurse through folder
    #     # TODO: Timeout problems?
    #     folders = driver.find_elements_by_class_name("section-summary")
    #     for folder in folders:
    #         link_el = folder.find_element_by_xpath(".//a")
    #         folder_href = link_el.get_attribute('href')
    #         folder_name = make_fs_string(link_el.text)
    #         section_queue.append(((course[0], os.path.join(course[1], folder_name), folder_href)))
    # except:
    #     print " :: :: Folder Search Faield!!!"


file_store = []
pages = courses + folder_queue + section_queue
for page in pages:
    # 1. Find single files
    driver.get(course[2])
    try:
        files = driver.find_elements_by_class_name("modtype_resource")
        for file in files:
            file_href = file.find_element_by_xpath(".//a").get_attribute('href')
            file_name = make_fs_string(file.find_element_by_class_name("instancename").text)
            file_store.append((course[0], course[1], file_name, file_href))
    except:
        print " :: :: No Files Found!"



print file_store
