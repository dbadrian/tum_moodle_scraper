from selenium import webdriver
import errno
import os
import requests
import argparse
import getpass
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
    args = parser.parse_args()


driver = webdriver.Chrome()
# On Windows, use: webdriver.PhantomJS('C:\phantomjs-1.9.7-windows\phantomjs.exe')

# Service selection
# Here I had to select my school among others
driver.get("https://www.moodle.tum.de/login/index.php")
a = driver.find_element_by_link_text('TUM LOGIN')
a.click()

# Fill the login form and submit it
driver.find_element_by_id('j_username').send_keys(args.user)
if args.pw:
    driver.find_element_by_id('j_password').send_keys(args.pw)
else:
    driver.find_element_by_id('j_password').send_keys(getpass.getpass("Please enter your password:"))
driver.find_element_by_id('Login').submit()

# Prepare for crawling mode
print "Storing Cookies"
session = requests.Session()
cookies = driver.get_cookies()
for cookie in cookies:
    session.cookies.set(cookie['name'], cookie['value'])

# We are now on the course pages
# Switch on to view all courses
driver.find_element_by_xpath("//select[@id='coc-filterterm']/option[@value='all']").click()


courses = driver.find_elements_by_class_name('coc-course')
course_list = []
for course in courses:
    term = course.find_element_by_class_name("termdiv").get_attribute('class').split(" ")[1].split("-")
    year = term[-2]
    sem = term[-1]
    folder = year + "_" + ("sose" if sem == 1 else "wise")
    a = course.find_element_by_xpath(".//h3/a")
    title = "_".join(a.get_attribute('title').split(" ")).lower()
    course_list.append((folder, title, a.get_attribute('href')))

# now process all the courses
file_store = []

driver.get(course_list[0][2])

# 1. Find all: Single Files
files = driver.find_elements_by_class_name("modtype_resource")
for file in files:
    file_href = file.find_element_by_xpath(".//a").get_attribute('href')
    file_name = make_fs_string(file.find_element_by_class_name("instancename").text)
    file_store.append((course_list[0][0], course_list[0][1], file_name, file_href))

# 1. Find all: Folders and repeat above


# Download Files
base = args.fn_out
for file in file_store:
    print "Processing: ", file[1], file[2]

    # Create Folder if it doesn't exist yet
    path = os.path.join(base, file[0], file[1])
    mkdir_p(path)

    # TODO CHECK IF FILE EXISTS ON FS BEFORE DOWNLOADING

    # Download File
    download_file(session, path, file[3])