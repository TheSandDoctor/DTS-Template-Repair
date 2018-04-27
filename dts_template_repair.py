#!/usr/bin/env python3.6
import mwclient, configparser, mwparserfromhell, argparse,re, pathlib
from time import sleep

def call_home(site):
    page = site.Pages['User:DeprecatedFixerBot/status']
    text = page.text()
    if "false" in text.lower():
        return False
    return True
def allow_bots(text, user):
    user = user.lower().strip()
    text = mwparserfromhell.parse(text)
    for tl in text.filter_templates():
        if tl.name in ('bots', 'nobots'):
            break
    else:
        return True
    for param in tl.params:
        bots = [x.lower().strip() for x in param.value.split(",")]
        if param.name == 'allow':
            if ''.join(bots) == 'none': return False
            for bot in bots:
                if bot in (user, 'all'):
                    return True
        elif param.name == 'deny':
            if ''.join(bots) == 'none': return True
            for bot in bots:
                if bot in (user, 'all'):
                    return False
    return True
def save_edit(page, utils, text):
    config,site,dry_run = utils
    original_text = text
    if not dry_run:
        if not allow_bots(original_text, config.get('enwikidep','username')):
            print("Page editing blocked as template preventing edit is present.")
            return
    code = mwparserfromhell.parse(text)
    for template in code.filter_templates():
        if ((template.name.matches("nobots") or template.name.matches("Wikipedia:Exclusion compliant"))
            and template.has("allow") and "DeprecatedFixerBot" in template.get("allow").value):
                    break # can edit
            print("\n\nPage editing blocked as template preventing edit is present.\n\n")
            return
    if not call_home(site):#config):
        raise ValueError("Kill switch on-wiki is false. Terminating program.")
    time = 0
    edit_summary = """'Removed deprecated link parameter from [[Template:Dts]] (or one of its redirects/aliases) using [[User:""" + config.get('enwikidep','username') + "| " + config.get('enwikidep','username') + """]]. Questions? [[User talk:TheSandDoctor|msg TSD!]] (please mention that this is task #4!)"""
    while True:
        if time == 1:
            """
            There was an edit error (probably an edit conflict),
            so best to refetch the page and rerun.
            """
            text = site.Pages[page.page_title].text()
        try:
            content_changed, text = process_page(original_text,dry_run)
        except ValueError as e:
            """
            To get here, there must have been an issue figuring out the
            contents for the parameter colwidth.

            At this point, it is safest just to print to console,
            record the error page contents to a file in ./errors and append
            to a list of page titles that has had
            errors (error_list.txt)/create a wikified version of error_list.txt
            and return out of this method.
            """
            print(e)
            pathlib.Path('./errors').mkdir(parents=False, exist_ok=True)
            title = get_valid_filename(page.page_title)
            text_file = open("./errors/err " + title + ".txt", "w")
            text_file.write("Error present: " +  str(e) + "\n\n\n\n\n" + text)
            text_file.close()
            text_file = open("./errors/error_list.txt", "a+")
            text_file.write(page.page_title + "\n")
            text_file.close()
            text_file = open("./errors/wikified_error_list.txt", "a+")
            text_file.write("#[[" + page.page_title + "]]" + "\n")
            text_file.close()
            return
        try:
            if dry_run:
                print("Dry run")
                #Write out the initial input
                title = get_valid_filename(page.page_title)
                text_file = open("./tests/in " + title + ".txt", "w")
                text_file.write(original_text)
                text_file.close()
                #Write out the output
                if content_changed:
                    title = get_valid_filename(page.page_title)
                    text_file = open("./tests/out " + title + ".txt", "w")
                    text_file.write(text)
                    text_file.close()
                else:
                    print("Content not changed, don't print output")
                break
            else:
                page.save(text, summary=edit_summary, bot=True, minor=True)
                print("Saved page")
        except [[EditError]]:
            print("Error")
            time = 1
            sleep(5)   # sleep for 5 seconds before trying again
            continue
        except [[ProtectedPageError]]:
            print('Could not edit ' + page.page_title + ' due to protection')
        break
def get_valid_filename(s):
    """
    Turns a regular string into a valid (sanatized) string that is safe for use
    as a file name.
    Method courtesy of cowlinator on StackOverflow
    (https://stackoverflow.com/questions/295135/turn-a-string-into-a-valid-filename)
    @param s String to convert to be file safe
    @return File safe string
    """
    assert(s is not "" or s is not None)
    s = str(s).strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', s)

def figure_type(template):
    """
    Figure out the type (name) of the template in question. This was originally
    in process_page(), but it became unwieldy.
    Returns false if the template is none of the ones we are looking for.
    """
    if template.name.matches("dts"):
        return "dts"
    elif template.name.matches("datesort"):
        return "datesort"
    elif template.name.matches("sbd"):
        return "sbd"
    elif template.name.matches("sortable date"):
        return "sortable date"
    elif template.name.matches("sortdate"):
        return "sortdate"
    else:
        return False

def process_page(text,dry_run):
    """
    Processes the page and removes the link parameter from
    dts template (and its redirects/aliases).
    @returns list containing content_changed flag and str casted code
    It raises a ValueError
    in the event that something went wrong (most likely an edit error or
    insufficient permissions).
    """
    wikicode = mwparserfromhell.parse(text)
    templates = wikicode.filter_templates()
    content_changed = False

    code = mwparserfromhell.parse(text) # parse WikiCode on page
    for template in code.filter_templates():
        type = figure_type(template)
        if(type):
            try:
                if template.has("link"):
                    template.remove("link")
                    content_changed = True
                print("Link removed")
            except ValueError:
                raise   # deal with this at a higher level
    return [content_changed, str(code)] # get back text to save

def single_run(title, utils, site):
    if title is None or title is "":
        raise ValueError("Category name cannot be empty!")
    if utils is None:
        raise ValueError("Utils cannot be empty!")
    if site is None:
        raise ValueError("Site cannot be empty!")
    print(title)
    page = site.Pages[title]
    text = page.text()

    try:
        save_edit(page, utils, text)
    except ValueError as err:
        print(err)
def category_run(cat_name, utils, site, offset,limited_run,pages_to_run):
    if cat_name is None or cat_name is "":
        raise ValueError("Category name cannot be empty!")
    if utils is None:
        raise ValueError("Utils cannot be empty!")
    if site is None:
        raise ValueError("Site cannot be empty!")
    if offset is None:
        raise ValueError("Offset cannot be empty!")
    if limited_run is None:
        raise ValueError("limited_run cannot be empty!")
    if pages_to_run is None:
        raise ValueError("""Seriously? How are we supposed to run pages in a
        limited test if none are specified?""")
    counter = 0
    for page in site.Categories[cat_name]:
        if offset > 0:
            offset -= 1
            print("Skipped due to offset config")
            continue
        print("Working with: " + page.name + " " + str(counter))
        if limited_run:
            if counter < pages_to_run:
                counter += 1
                text = page.text()
                try:
                    save_edit(page, utils, text)
                except ValueError as err:
                    print(err)
            else:
                return  # run out of pages in limited run
def main():
    dry_run = False
    pages_to_run = 80
    offset = 0
    category = "Dts templates with deprecated parameters"
    limited_run = True

    parser = argparse.ArgumentParser(prog='DeprecatedFixerBot Music infobox fixer', description='''Adds "subst:" to the beginning of all
    {{infobox album}}, {{extra chronology}}, {{extra album cover}}, and {{extra track listing}} templates. This results in the template substitution trick which replaces deprecated parameters with their correct values to occur.''')
    parser.add_argument("-dr", "--dryrun", help="perform a dry run (don't actually edit)",
                    action="store_true")
    args = parser.parse_args()
    if args.dryrun:
        dry_run = True
        print("Dry run")

    site = mwclient.Site(('https','en.wikipedia.org'), '/w/')
    if dry_run:
        pathlib.Path('./tests').mkdir(parents=False, exist_ok=True)
    config = configparser.RawConfigParser()
    config.read('credentials.txt')
    try:
        #pass
        site.login(config.get('enwikidep','username'), config.get('enwikidep', 'password'))
    except errors.LoginError as e:
        print(e)
        raise ValueError("Login failed.")

    utils = [config,site,dry_run]
    try:
        category_run(category, utils, site, offset,limited_run,pages_to_run)
    except ValueError as e:
        print("\n\n" + str(e))

if __name__ == "__main__":
    main()
