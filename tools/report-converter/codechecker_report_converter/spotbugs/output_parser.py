# -------------------------------------------------------------------------
#
#  Part of the CodeChecker project, under the Apache License v2.0 with
#  LLVM Exceptions. See LICENSE for license information.
#  SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
#
# -------------------------------------------------------------------------

import logging
import os
import xml.etree.ElementTree as ET

from ..output_parser import Message, Event, BaseParser

LOG = logging.getLogger('ReportConverter')


class SpotBugsMessage(Message):
    """ Represents a message with an optional event, fixit and note messages.

    This will be a diagnostic section in the plist which represents a report.
    """

    def __init__(self, path, line, column, message, checker, report_hash,
                 events=None, notes=None, fixits=None):
        super(SpotBugsMessage, self).__init__(path, line, column, message,
                                              checker, events, notes, fixits)
        self.report_hash = report_hash

    def __eq__(self, other):
        return super(SpotBugsMessage, self).__eq__(other) and \
            self.report_hash == other.report_hash

    def __str__(self):
        return '%s, report_hash=%s' % \
               (super(SpotBugsMessage, self).__str__(), self.report_hash)


class SpotBugsParser(BaseParser):
    """ Parser for SpotBugs output. """

    def __init__(self):
        super(SpotBugsParser, self).__init__()
        self.project_paths = []

    def parse_messages(self, analyzer_result):
        """ Parse the given analyzer result. """

        root = self.__parse_analyzer_result(analyzer_result)
        if root is None:
            return

        self.project_paths = self.__get_project_paths(root)

        for bug in root.findall('BugInstance'):
            message = self.__parse_bug(bug)
            if message:
                self.messages.append(message)

        return self.messages

    def __get_abs_path(self, source_path):
        """ Returns full path of the given source path.

        It will try to find the given source path in the project paths and
        returns full path if it founds.
        """
        if os.path.exists(source_path):
            return source_path

        for project_path in self.project_paths:
            full_path = os.path.join(project_path, source_path)
            if os.path.exists(full_path):
                return full_path

        LOG.warning("No source file found: %s", source_path)

    def __parse_analyzer_result(self, analyzer_result):
        """ Parse the given analyzer result xml file.

        Returns the root element of the parsed tree or None if something goes
        wrong.
        """
        try:
            tree = ET.parse(analyzer_result)
            return tree.getroot()
        except OSError:
            LOG.error("Analyzer result does not exist: %s", analyzer_result)
        except ET.ParseError:
            LOG.error("Failed to parse the given analyzer result '%s'. Please "
                      "give a valid xml file with messages generated by "
                      "SpotBugs.", analyzer_result)

    def __get_project_paths(self, root):
        """ Get project paths from the bug collection. """
        paths = []

        project = root.find('Project')
        for element in project:
            file_path = element.text
            if os.path.isdir(file_path):
                paths.append(file_path)
            elif os.path.isfile(file_path):
                paths.append(os.path.dirname(file_path))

        return paths

    def __parse_bug(self, bug):
        """ Parse the given bug and create a message from them. """
        report_hash = bug.attrib.get('instanceHash')
        checker_name = bug.attrib.get('type')

        long_message = bug.find('LongMessage').text

        source_line = bug.find('SourceLine')
        source_path = source_line.attrib.get('sourcepath')
        source_path = self.__get_abs_path(source_path)
        if not source_path:
            return

        line = source_line.attrib.get('start')
        col = 0

        events = []
        for element in list(bug):
            event = None
            if element.tag == 'Class':
                event = self.__event_from_class(element)
            elif element.tag == 'Method':
                event = self.__event_from_method(element)

            if event:
                events.append(event)

        return SpotBugsMessage(source_path, int(line), col, long_message,
                               checker_name, report_hash, events)

    def __event_from_class(self, element):
        """ Creates event from a Class element. """
        message = element.find('Message').text

        source_line = element.find('SourceLine')
        if source_line is None:
            return

        source_path = source_line.attrib.get('sourcepath')
        source_path = self.__get_abs_path(source_path)
        if not source_path:
            return

        line = source_line.attrib.get('start')
        col = 0

        return Event(source_path, int(line), col, message)

    def __event_from_method(self, element):
        """ Creates event from a Method element. """
        message = element.find('Message').text

        source_line = element.find('SourceLine')
        if source_line is None:
            return

        source_path = source_line.attrib.get('sourcepath')
        source_path = self.__get_abs_path(source_path)
        if not source_path:
            return

        line = source_line.attrib.get('start')
        col = 0

        return Event(source_path, int(line), col, message)
