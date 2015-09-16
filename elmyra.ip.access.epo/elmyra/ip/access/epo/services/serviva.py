# -*- coding: utf-8 -*-
# (c) 2015 Andreas Motl, Elmyra UG
import json
import logging
from cornice.service import Service
from pymongo.errors import OperationFailure
from pyramid.httpexceptions import HTTPNotFound, HTTPBadRequest
from pyramid.settings import asbool
from elmyra.ip.access.serviva.api import serviva_download
from elmyra.ip.access.serviva.dataproxy import serviva_published_data_search, LoginException, SearchException, serviva_published_data_crawl, ServivaException, ServivaFormatException
from elmyra.ip.access.serviva.expression import should_be_quoted
from elmyra.ip.util.python import _exception_traceback
#from elmyra.ip.util.cql.util import should_be_quoted

log = logging.getLogger(__name__)

sdp_download_service = Service(
    name='sdp-download',
    path='/api/sdp/download/{resource}.{format}',
    description="SDP download interface")
sdp_published_data_search_service = Service(
    name='sdp-published-data-search',
    path='/api/sdp/published-data/search',
    description="SDP search interface")
sdp_published_data_crawl_service = Service(
    name='sdp-published-data-crawl',
    path='/api/sdp/published-data/crawl{dummy1:\/?}{constituents:.*?}',
    description="SDP crawler interface")


@sdp_download_service.get(renderer='null')
def sdp_download_handler(request):
    """Download resources from Serviva Data Proxy"""

    resource = request.matchdict['resource']
    format   = request.matchdict['format'].lower()
    pretty   = asbool(request.params.get('pretty'))
    seq      = int(request.params.get('seq', 1))
    options = {'pretty': pretty, 'seq': seq}

    try:
        serviva_response = serviva_download(resource, format, options)

    except ServivaException, ex:
        if type(ex) is ServivaFormatException:
            raise HTTPNotFound(ex)
        else:
            raise HTTPBadRequest(ex)


    if serviva_response.payload:

        request.response.content_type = serviva_response.mimetype

        # http://tools.ietf.org/html/rfc6266#section-4.2
        disposition = serviva_response.disposition_inline and 'inline' or 'attachment'

        content_disposition = '{disposition}; filename={filename}'.format(disposition=disposition, filename=serviva_response.filename)
        request.response.headers['Content-Disposition'] = content_disposition
        request.response.headers['Data-Source'] = 'sdp'

        return serviva_response.payload

    else:

        raise HTTPNotFound("Resource '%s' with format='%s' not found" % (resource, format))


@sdp_published_data_search_service.get(accept="application/json")
def sdp_published_data_search_handler(request):
    """Search for published-data at Serviva Data Proxy"""

    # query expression
    query = request.params.get('query', '')
    log.info('query raw: ' + query)

    # fixup query: wrap into quotes if cql string is a) unspecific, b) contains spaces and c) is still unquoted
    if should_be_quoted(query):
        query = '"%s"' % query

    #propagate_keywords(request, query_object)

    # lazy-fetch more entries
    # TODO: get from elmyra.ip.access.serviva
    limit = 250
    offset_local = int(request.params.get('range_begin', 0))
    offset_remote = int(offset_local / limit) * limit

    try:
        data = serviva_published_data_search(query, offset_remote, limit)
        return data

    except LoginException as ex:
        request.errors.add('SDP', 'login', ex.details)

    except SearchException as ex:
        message = unicode(ex.message)
        if hasattr(ex, 'details'):
            message += ': ' + ex.details
        request.errors.add('SDP', 'search', message)

    except SyntaxError as ex:
        request.errors.add('SDP', 'query', unicode(ex.msg))

    except OperationFailure as ex:
        log.error(ex)
        message = unicode(ex)
        request.errors.add('SDP', 'query', message)


@sdp_published_data_crawl_service.get(accept="application/json")
def sdp_published_data_crawl_handler(request):
    """Crawl published-data at SDP"""

    # query expression
    query = request.params.get('query', '')
    log.info('query raw: ' + query)

    if should_be_quoted(query):
        query = '"%s"' % query

    # constituents: abstract, biblio and/or full-cycle
    constituents = request.matchdict.get('constituents', 'full-cycle')
    print 'constituents:', constituents

    chunksize = int(request.params.get('chunksize', '5000'))

    try:
        result = serviva_published_data_crawl(constituents, query, chunksize)
        return result

    except Exception as ex:
        log.error(u'SDP crawler error: query="{0}", reason={1}, Exception was:\n{2}'.format(query, ex, _exception_traceback()))
        request.errors.add('sdp-published-data-crawl', 'query', str(ex))
