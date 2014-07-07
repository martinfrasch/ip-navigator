# -*- coding: utf-8 -*-
# (c) 2014 Andreas Motl, Elmyra UG
#
# CQL grammar based on pyparsing
# https://en.wikipedia.org/wiki/Contextual_Query_Language
#
# Derived from simpleSQL.py, Copyright (c) 2003, Paul McGuire
# http://pyparsing.wikispaces.com/file/view/simpleSQL.py
#
# See also:
#
# - http://pyparsing.wikispaces.com/HowToUsePyparsing
# - http://pyparsing.wikispaces.com/file/view/searchparser.py
#
import re
import logging
from pyparsing import \
    Word, \
    Literal, CaselessLiteral, \
    Keyword, CaselessKeyword, \
    Regex, \
    alphas, nums, alphanums, quotedString, \
    oneOf, upcaseTokens, delimitedList, restOfLine, \
    Forward, Group, Combine, Optional, ZeroOrMore, \
    NotAny, FollowedBy, StringEnd, \
    ParseResults, ParseException
from elmyra.ip.util.cql.pyparsing.util import get_literals


log = logging.getLogger(__name__)


# ------------------------------------------
#   A. characters
# ------------------------------------------

# DEPATISnet uses "?!#"
# TODO: check OPS
wildcards = u'?!#'

# - classification terms (IPC, CPC) may contain forward slashes and dashes, e.g. H04L12/433, F17D5-00
# - numeric terms may contain punctuation (,.), e.g. 2.45
# - dates may contain dashes, e.g. M11-2009
separators = u'/,.-'

# limited set of unicode characters
#umlauts = u'äöüÄÖÜß'

# all unicode characters
# http://stackoverflow.com/questions/2339386/python-pyparsing-unicode-characters/2340659#2340659
unicode_printables = u''.join(unichr(c) for c in xrange(65536) if unichr(c).isalnum() and not unichr(c).isspace())


# ------------------------------------------
#   B. symbols
# ------------------------------------------

# B.1 binary comparison operators
cmp_single = u'= != < > <= >='.split()
cmp_perl = u'eq ne lt gt le ge'.split()
cmp_cql = u'exact within encloses all any any/relevant any/rel.lr'.split()
binop_symbols = cmp_single + cmp_perl + cmp_cql

# B.2 boolean operators
and_ = CaselessKeyword("and") | CaselessKeyword("UND")
or_ = CaselessKeyword("or") | CaselessKeyword("ODER")
not_ = CaselessKeyword("not") | CaselessKeyword("NICHT")
prox_ = CaselessKeyword("prox") | CaselessKeyword("NAHE")
booleans = get_literals(and_, or_, not_, prox_)

# B.3 neighbourhood term operators
# see also:
# - https://depatisnet.dpma.de/depatisnet/htdocs/prod/de/hilfe/recherchemodi/experten-recherche/
# - https://depatisnet.dpma.de/depatisnet/htdocs/prod/en/hilfe/recherchemodi/experten-recherche/

# v1: this would work for simple term operators only
#termop = oneOf("(W) (NOTW) (A) (P) (L)", caseless=True).setName("termop")

# v2: use regexes for describing term operators like "(10A)"
neighbourhood_symbols = '(W) (NOTW) (#W) (A) (#A) (P) (L)'.split()
neighbourhood_symbols = ['\s?' + re.escape(symbol).replace('\#', '\d+') + '\s?' for symbol in neighbourhood_symbols]


# ------------------------------------------
#   C. building blocks
# ------------------------------------------
termop = Regex( "|".join(neighbourhood_symbols), re.IGNORECASE ).setParseAction( upcaseTokens ).setName("termop")
termword = Word(unicode_printables + separators + wildcards).setName("term")


# ------------------------------------------
#   D. triple
# ------------------------------------------
index = Word(alphanums).setName("index")
binop = oneOf(binop_symbols, caseless=True).setName("binop")
term  = ( Combine(termword + ZeroOrMore( termop + termword )).setName("term") ^ quotedString.setName("term") )


# ------------------------------------------
#   E. condition
# ------------------------------------------
cqlStatement = Forward()

# Parse regular cql condition notation 'index=term'.
cqlConditionBase = Group(

    # a regular triple
    ( index + binop + term ).setResultsName("triple") |

    # a regular subquery
    ( "(" + cqlStatement + ")" ).setResultsName("subquery")
)

# Parse value shortcut notations like 'index=(term)' or 'index=(term1 and term2 or term3)'.
cqlConditionShortcut = Group(

    # a triple in value shortcut notation (contains only the single term)
    # "term + NotAny(binop)" helps giving proper error messages like
    # "ParseException: Expected term (at char 4)" for erroneous queries like "foo="
    ( term + NotAny(binop) ).setResultsName("triple-short") |

    # a subquery containing values in shortcut notation
    ( index + binop + "(" + cqlStatement + ")" ).setResultsName("subquery-short")

)

#cqlCondition = cqlConditionBase
cqlCondition = cqlConditionBase | cqlConditionShortcut


# ------------------------------------------
#   F. statement
# ------------------------------------------

cqlStatement << cqlCondition + ZeroOrMore( ( and_ | or_ | not_ | prox_ ) + cqlStatement )

# apply SQL comment format
cqlComment = "--" + restOfLine
cqlStatement.ignore(cqlComment)



def parse_cql(cql, logging=True):
    """
    Parse a CQL query string.

    >>> tokens = parse_cql('foo=bar')
    >>> tokens
    ([(['foo', u'=', 'bar'], {'triple': [((['foo', u'=', 'bar'], {}), 0)]})], {})

    """

    tokens = []
    try:
        # make sure the whole query is parsed, otherwise croak
        tokens = cqlStatement.parseString(cql, parseAll=True)
        #tokens.pprint()

    except ParseException as ex:
        ex.explanation = '%s\n%s\n%s' % (cql, ' ' * ex.loc + '^\n', ex)
        if logging:
            log.error('\n%s', ex.explanation)
        raise

    return tokens
