# -*- coding: utf-8 -*-
# (c) 2014 Andreas Motl, Elmyra UG
import logging
from cornice.service import Service
from elmyra.ip.util.crypto.jwt import JwtSigner, JwtVerifyError, ISigner
from pyramid.httpexceptions import HTTPBadRequest
from simplejson.scanner import JSONDecodeError
from zope.interface.declarations import implements
from zope.interface.interface import Interface


log = logging.getLogger(__name__)

def includeme(config):

    # register a signer object used throughout this place
    signer = JwtSigner()
    signer.genkey('12345', salt='elmyra.ipsuite.navigator.opaquelinks', keysize=1024)
    config.registry.registerUtility(signer)

    # attempt to decode opaque parameter tokens on each request
    config.add_subscriber(create_request_interceptor, 'pyramid.events.ContextFound')


# ------------------------------------------
#   hooks
# ------------------------------------------
def create_request_interceptor(event):
    """
    Intercept "op" (opaque parameters) request parameter,
    decode it and serve as ``request.opaque`` dictionary.
    """
    request = event.request

    request.opaque = {}

    # extract opaque parameters token from request
    op_token = request.params.get('op')

    # do nothing if no token given
    if not op_token:
        return

    registry = event.request.registry
    signer = registry.getUtility(ISigner)

    try:
        data = signer.unsign(op_token)
        if data:
            request.opaque.update(data)
        else:
            log.error('opaque parameter token is empty. data=%s, token=%s', data, op_token)

    except JwtVerifyError as ex:
        log.error('Error while decoding opaque parameter token: %s', ex.message)


# ------------------------------------------
#   services
# ------------------------------------------
opaquelinks_token_service = Service(
    name='opaquelinks-token',
    path='/api/opaquelinks/token',
    description="opaquelinks token generator")

opaquelinks_verify_service = Service(
    name='opaquelinks-verify',
    path='/api/opaquelinks/token/verify',
    description="opaquelinks token verifier")


# ------------------------------------------
#   service handlers
# ------------------------------------------
@opaquelinks_token_service.post(accept="application/json")
def opaquelinks_token_handler(request):
    """Generate an opaquelinks token"""
    payload = request_payload(request)
    signer = request.registry.getUtility(ISigner)
    return signer.sign(payload)


@opaquelinks_verify_service.post(accept="application/json")
def opaquelinks_verify_handler(request):
    """Verify an opaquelinks token"""

    token = token_payload(request)

    if not token:
        return HTTPBadRequest('Token missing')

    signer = request.registry.getUtility(ISigner)
    return signer.unsign(token)


# ------------------------------------------
#   utility functions
# ------------------------------------------
def request_payload(request):
    payload = {}
    if request.content_type == 'application/json':
        try:
            payload = request.json
        except JSONDecodeError as error:
            log.error('Could not derive data from json request: %s body=%s', error, request.body)

    payload.update(dict(request.params))
    return payload

def token_payload(request):
    token = None
    if request.content_type == 'application/json':

        try:
            token = str(request.json)
        except JSONDecodeError as error:
            log.error('Could not extract token from json request: %s body=%s', error, request.body)

    if not token:
        log.error('Could not extract token from request: content-type=%s, body=%s', request.content_type, request.body)

    return token
