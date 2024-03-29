"""
Houses the wrapper for wmi-client.

There are a handful of injection vulnerabilities in this, so don't expose it
directly to end-users.
"""

import csv
import sh
import re
from StringIO import StringIO

def getEventDict(estr):
    fields = estr.split("\x01")
    return {
	'Category' : fields[0],
    	'CategoryString' : fields[1],
    	'ComputerName' : fields[2],
    	'Data' : fields[3],
    	'EventCode' : fields[4],
    	'EventIdentifier' : fields[5],
    	'EventType' : fields[6],
    	'InsertionStrings' : fields[7],
    	'Logfile' : fields[8],
    	#'Message' : fields[9],
    	'RecordNumber' : fields[10],
    	'SourceName' : fields[11],
    	'TimeGenerated' : fields[12],
    	'TimeWritten' : fields[13],
    	'Type' : fields[14],
    	'User' : fields[15]
    }

class WmiClientWrapper(object):
    """
    Wrap wmi-client. Creating an instance of the wrapper will make a security
    context through which all future queries will be executed. It's basically
    just a convenient way to remember the username, password and host.

    There are a handful of injection vulnerabilities in this, so don't expose
    it directly to end-users.
    """

    def __init__(self, username="Administrator", password=None, host=None, delimiter="\01"):
        assert username
        assert password
        assert host # assume host is up

        # store the credentials for later
        self.username = username
        self.password = password
        self.host = host

        self.delimiter = delimiter

    def _make_credential_args(self):
        """
        Makes credentials that get passed to wmic. This assembles a list of
        arguments.
        """
        arguments = []

        # the format is user%pass
        # NOTE: this is an injection vulnerability
        userpass = "--user={username}%{password}".format(
            username=self.username,
            password=self.password,
        )

        arguments.append(userpass)

        # the format for ip addresses and host names is //
        hostaddr = "//{host}".format(host=self.host)

        arguments.append(hostaddr)

        return arguments

    def _setup_params(self):
        """
        Makes extra configuration that gets passed to wmic.
        """
        return ["--delimiter={delimiter}".format(delimiter=self.delimiter)]

    def _construct_query(self, klass):
        """
        Makes up a WMI query based on a given class.
        """
        # NOTE: this is an injection vulnerability
        queryx = "SELECT * FROM {klass}".format(klass=klass)
        return queryx

    def query(self, klass):
        """
        Executes a query using the wmi-client command.
        """
        # i don't want to have to repeat the -U stuff
        credentials = self._make_credential_args()

        # Let's make the query construction independent, but also if there's a
        # space then it's probably just a regular query.
        if " " not in klass:
            queryx = self._construct_query(klass)
        else:
            queryx = klass

        # and these are just configuration
        setup = self._setup_params()

        # construct the arguments to wmic
        arguments = setup + credentials + [queryx]

        # execute the command
        output = sh.wmic(*arguments)

        # just to be sure? sh is weird sometimes.
        output = str(output)

        # and now parse the output
	return WmiClientWrapper._parse_wmic_output(output, delimiter=self.delimiter)

    @classmethod
    def _parse_wmic_output(cls, output, delimiter="\01"):
        """
        Parses output from the wmic command and returns json.
        """
        # remove newlines and whitespace from the beginning and end
	output = output.strip()

        # Quick parser hack- make sure that the initial file or section is also
        # counted in the upcoming split.
        if output[:7] == "CLASS: ":
            output = "\n" + output

        # There might be multiple files in the output. Track how many there
        # should be so that errors can be raised later if something is
        # inconsistent.
        expected_sections_count = output.count("\nCLASS: ")

        # Split up the file into individual sections. Each one corresponds to a
        # separate csv file.
        sections = output.split("\nCLASS: ")
	

        # The split causes an empty string as the first member of the list and
        # it should be removed because it's junk.
        if sections[0] == "":
            sections = sections[1:]

        assert len(sections) is expected_sections_count

        items = []
        for section in sections:
            # remove the first line because it has the query class
            strio = StringIO(section)
	    strings = strio.read().splitlines()[2:]
	    #section = "@@@".join(section.splitlines()[2:])
	    event_parts = []
	    for string in strings:
	        pstr = string.strip()
		if not pstr:
		    continue
		if (pstr[:5]).isdigit():
		    if event_parts:
		        event = ' '.join(event_parts)
			ev = getEventDict(event)
			items.append(ev)
	                event_parts = []
		    event_parts.append(pstr)
		else:
		    event_parts.append(pstr)
		

            #moredata = list(csv.DictReader(strio, delimiter=delimiter))
	    #print 'MOREDATA', moredata

        # walk the dictionaries!
        return WmiClientWrapper._fix_dictionary_output(items)

    @classmethod
    def _fix_dictionary_output(cls, incoming):
        """
        The dictionary doesn't exactly match the traditional python-wmi output.
        For example, there's "True" instead of True. Integer values are also
        quoted. Values that should be "None" are "(null)".

        This can be fixed by walking the tree.

        The Windows API is able to return the types, but here we're just
        guessing randomly. But guessing should work in most cases. There are
        some instances where a value might happen to be an integer but has
        other situations where it's a string. In general, the rule of thumb
        should be to cast to whatever you actually need, instead of hoping that
        the output will always be an integer or will always be a string..
        """

        if isinstance(incoming, list):
            output = []

            for each in incoming:
                output.append(cls._fix_dictionary_output(each))

        elif isinstance(incoming, dict):
            output = dict()

            for (key, value) in incoming.items():
		if key == "TimeGenerated":
		    output[key] = value.split('.')[0]
                elif value == "(null)":
                    output[key] = None
                elif value == "True":
                    output[key] = True
                elif value == "False":
                    output[key] = False
                elif isinstance(value, str) and len(value) > 1 and value[0] == "(" and value[-1] == ")":
                    # convert to a list with a single entry
                    output[key] = [value[1:-1]]
                elif isinstance(value, str):
                    output[key] = value
                elif isinstance(value, dict):
                    output[key] = cls._fix_dictionary_output(value)

        return output
