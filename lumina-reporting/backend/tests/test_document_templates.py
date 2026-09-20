"""The template API: what the canvas loads and saves.

The point of interest is not the CRUD -- it is that the API refuses exactly
the trees the renderer refuses, and that a save replaces a tree wholesale
rather than merging it. Both are tested against the endpoint rather than the
helper, because the helper being right is not the same as the route calling it.
"""

import json

from database import db_session
from schema_v2 import DocumentTemplate, TemplateElement, TemplateSection


def _tree(**overrides):
    """A small, valid template: a repeating footer band and a flow body."""
    payload = {
        'name': 'Quarterly Factsheet',
        'code': 'quarterly-factsheet',
        'description': 'One page per share class.',
        'page': {
            'size': 'a4',
            'orientation': 'portrait',
            'margins': {'top': 26, 'bottom': 20, 'left': 16, 'right': 16},
        },
        'sections': [
            {
                'ordinal': 0,
                'name': 'Body',
                'layout_mode': 'flow',
                'elements': [
                    {
                        'element_type': 'text',
                        'x_mm': 0, 'y_mm': 0, 'w_mm': 178, 'h_mm': 12,
                        'static_text': 'Performance',
                        'style_token': 'heading-1',
                        'options': {'align': 'left', 'color': 'primary'},
                    },
                    {
                        'element_type': 'field',
                        'x_mm': 0, 'y_mm': 14, 'w_mm': 90, 'h_mm': 6,
                        'binding_kind': 'system',
                        'binding_key': 'client_name',
                    },
                ],
            },
            {
                'ordinal': 1,
                'name': 'Footer',
                'layout_mode': 'fixed',
                'height_mm': 12,
                'repeat_mode': 'every_page',
                'elements': [
                    {
                        'element_type': 'page_number',
                        'x_mm': 150, 'y_mm': 3, 'w_mm': 28, 'h_mm': 6,
                        'binding_kind': 'system',
                        'binding_key': 'page_number',
                    },
                ],
            },
        ],
    }
    payload.update(overrides)
    return payload


def _create(client, headers, **overrides):
    return client.post('/api/document-templates', json=_tree(**overrides), headers=headers)


def test_create_returns_the_tree_that_was_written(client, auth_headers):
    response = _create(client, auth_headers)
    assert response.status_code == 201, response.get_json()
    body = response.get_json()

    assert body['name'] == 'Quarterly Factsheet'
    assert body['version'] == 1
    assert body['is_published'] is False
    assert body['page']['margins']['top'] == 26
    assert [section['name'] for section in body['sections']] == ['Body', 'Footer']
    assert [element['element_type'] for element in body['sections'][0]['elements']] == [
        'text', 'field']
    assert body['sections'][1]['height_mm'] == 12
    assert body['sections'][1]['repeat_mode'] == 'every_page'


def test_millimetres_survive_the_round_trip(client, auth_headers):
    """The canvas works in fractional millimetres; a column that rounded them
    would move every element a hair on the first save."""
    created = _create(client, auth_headers).get_json()
    template_id = created['id']

    created['sections'][0]['elements'][0]['x_mm'] = 12.345
    created['sections'][0]['elements'][0]['w_mm'] = 101.5
    client.put(f'/api/document-templates/{template_id}', json=created, headers=auth_headers)

    fetched = client.get(f'/api/document-templates/{template_id}',
                         headers=auth_headers).get_json()
    element = fetched['sections'][0]['elements'][0]
    assert element['x_mm'] == 12.345
    assert element['w_mm'] == 101.5


def test_list_shows_templates_without_their_trees(client, auth_headers):
    _create(client, auth_headers)
    body = client.get('/api/document-templates', headers=auth_headers).get_json()
    assert len(body) == 1
    # The list is a picker, not a load: sending every element of every
    # template to draw a menu is the kind of thing that only hurts later.
    assert 'sections' not in body[0]


def test_save_replaces_the_tree_rather_than_merging_it(app, client, auth_headers):
    created = _create(client, auth_headers).get_json()
    template_id = created['id']

    created['sections'] = [{
        'ordinal': 0,
        'name': 'Only Band',
        'layout_mode': 'flow',
        'elements': [{
            'element_type': 'image',
            'x_mm': 0, 'y_mm': 0, 'w_mm': 40, 'h_mm': 20,
        }],
    }]
    response = client.put(f'/api/document-templates/{template_id}',
                          json=created, headers=auth_headers)
    assert response.status_code == 200, response.get_json()
    assert [section['name'] for section in response.get_json()['sections']] == ['Only Band']

    with app.app_context():
        # The old rows are gone, not orphaned. An element left behind with a
        # dangling section_id renders as nothing and audits as a mystery.
        assert db_session.query(TemplateSection).count() == 1
        assert db_session.query(TemplateElement).count() == 1


def test_options_round_trip_as_json(client, auth_headers):
    created = _create(client, auth_headers).get_json()
    created['sections'][0]['elements'][0]['options'] = {
        'align': 'center', 'border': 'bottom', 'fill': 'tint'}
    client.put(f'/api/document-templates/{created["id"]}',
               json=created, headers=auth_headers)

    fetched = client.get(f'/api/document-templates/{created["id"]}',
                         headers=auth_headers).get_json()
    assert fetched['sections'][0]['elements'][0]['options'] == {
        'align': 'center', 'border': 'bottom', 'fill': 'tint'}


def test_name_and_code_are_required(client, auth_headers):
    response = client.post('/api/document-templates', json={'name': 'No code'},
                           headers=auth_headers)
    assert response.status_code == 400
    assert 'code' in response.get_json()['message']


def test_a_css_declaration_is_not_a_style_token(client, auth_headers):
    """The whole point of a token is that a template cannot smuggle CSS into
    the renderer. If the API accepted one, the brand kit would be advisory."""
    payload = _tree()
    payload['sections'][0]['elements'][0]['style_token'] = 'font-size: 40px'
    response = client.post('/api/document-templates', json=payload, headers=auth_headers)
    assert response.status_code == 400
    assert 'unknown style token' in response.get_json()['message']


def test_a_style_token_outside_the_vocabulary_is_refused(client, auth_headers):
    """Not just CSS -- a plausible-looking name the renderer has no rule for
    would draw body text while the canvas showed a heading."""
    payload = _tree()
    payload['sections'][0]['elements'][0]['style_token'] = 'heading-7'
    response = client.post('/api/document-templates', json=payload, headers=auth_headers)
    assert response.status_code == 400
    assert 'heading-7' in response.get_json()['message']


def test_an_unknown_option_key_is_reported_not_dropped(client, auth_headers):
    payload = _tree()
    payload['sections'][0]['elements'][0]['options'] = {'alignment': 'center'}
    response = client.post('/api/document-templates', json=payload, headers=auth_headers)
    assert response.status_code == 400
    assert "unknown option 'alignment'" in response.get_json()['message']


def test_an_option_value_outside_its_vocabulary_is_refused(client, auth_headers):
    payload = _tree()
    payload['sections'][0]['elements'][0]['options'] = {'color': '#ff0000'}
    response = client.post('/api/document-templates', json=payload, headers=auth_headers)
    assert response.status_code == 400
    # A hex is exactly what the role vocabulary exists to keep out: an
    # element carrying one keeps drawing the old brand after a rebrand.
    assert 'color=' in response.get_json()['message']


def test_a_repeating_band_cannot_sit_in_the_middle_of_the_flow(client, auth_headers):
    payload = _tree()
    payload['sections'].append({
        'ordinal': 2, 'name': 'Tail', 'layout_mode': 'flow', 'elements': [],
    })
    response = client.post('/api/document-templates', json=payload, headers=auth_headers)
    assert response.status_code == 400
    # The footer is now section 1 of 3 -- neither first nor last.
    assert 'repeating band' in response.get_json()['message']


def test_a_fixed_band_must_declare_a_height(client, auth_headers):
    payload = _tree()
    payload['sections'][1]['height_mm'] = None
    response = client.post('/api/document-templates', json=payload, headers=auth_headers)
    assert response.status_code == 400
    assert 'height' in response.get_json()['message']


def test_an_unknown_element_type_is_a_400_not_a_500(client, auth_headers):
    """`renderers.layout.validate` indexes the keys it needs. A submitted
    element missing `element_type` used to reach it as a KeyError."""
    payload = _tree()
    del payload['sections'][0]['elements'][0]['element_type']
    response = client.post('/api/document-templates', json=payload, headers=auth_headers)
    assert response.status_code == 400
    assert 'element type' in response.get_json()['message']


def test_an_unknown_system_binding_is_refused(client, auth_headers):
    payload = _tree()
    payload['sections'][0]['elements'][1]['binding_key'] = 'client_tax_id'
    response = client.post('/api/document-templates', json=payload, headers=auth_headers)
    assert response.status_code == 400
    assert 'client_tax_id' in response.get_json()['message']


def test_every_problem_in_one_reply(client, auth_headers):
    payload = _tree()
    payload['sections'][0]['elements'][0]['style_token'] = 'color: red'
    payload['sections'][0]['elements'][1]['binding_key'] = 'nonsense'
    payload['page']['size'] = 'a7'
    message = client.post('/api/document-templates', json=payload,
                          headers=auth_headers).get_json()['message']
    assert 'a7' in message and 'color: red' in message and 'nonsense' in message


def test_nothing_is_written_when_a_tree_is_refused(app, client, auth_headers):
    payload = _tree()
    payload['sections'][0]['elements'][0]['style_token'] = 'color: red'
    client.post('/api/document-templates', json=payload, headers=auth_headers)
    with app.app_context():
        assert db_session.query(DocumentTemplate).count() == 0
        assert db_session.query(TemplateSection).count() == 0


def test_a_published_template_cannot_be_edited(client, auth_headers):
    created = _create(client, auth_headers).get_json()
    published = client.post(f'/api/document-templates/{created["id"]}/publish',
                            headers=auth_headers)
    assert published.status_code == 200
    assert published.get_json()['is_published'] is True

    response = client.put(f'/api/document-templates/{created["id"]}',
                          json=created, headers=auth_headers)
    assert response.status_code == 409
    assert 'new version' in response.get_json()['message']


def test_an_empty_template_cannot_be_published(client, auth_headers):
    created = _create(client, auth_headers, sections=[]).get_json()
    response = client.post(f'/api/document-templates/{created["id"]}/publish',
                           headers=auth_headers)
    assert response.status_code == 400


def test_a_new_version_copies_the_tree_and_leaves_the_published_one_alone(
        client, auth_headers):
    created = _create(client, auth_headers).get_json()
    client.post(f'/api/document-templates/{created["id"]}/publish', headers=auth_headers)

    response = client.post(f'/api/document-templates/{created["id"]}/versions',
                           headers=auth_headers)
    assert response.status_code == 201
    clone = response.get_json()
    assert clone['id'] != created['id']
    assert clone['code'] == created['code']
    assert clone['version'] == 2
    assert clone['is_published'] is False
    assert [section['name'] for section in clone['sections']] == ['Body', 'Footer']
    assert (clone['sections'][0]['elements'][0]['static_text']
            == created['sections'][0]['elements'][0]['static_text'])

    # Editing the clone must not touch what a distributed pack rendered from.
    clone['sections'] = []
    client.put(f'/api/document-templates/{clone["id"]}', json=clone, headers=auth_headers)
    original = client.get(f'/api/document-templates/{created["id"]}',
                          headers=auth_headers).get_json()
    assert len(original['sections']) == 2


def test_versions_keep_counting_up(client, auth_headers):
    created = _create(client, auth_headers).get_json()
    second = client.post(f'/api/document-templates/{created["id"]}/versions',
                         headers=auth_headers).get_json()
    # Branched from v1 again -- the next number still has to be 3, or two
    # rows would claim to be version 2 of the same code.
    third = client.post(f'/api/document-templates/{created["id"]}/versions',
                        headers=auth_headers).get_json()
    assert (second['version'], third['version']) == (2, 3)


def test_delete_is_soft(app, client, auth_headers):
    created = _create(client, auth_headers).get_json()
    assert client.delete(f'/api/document-templates/{created["id"]}',
                         headers=auth_headers).status_code == 200

    assert client.get(f'/api/document-templates/{created["id"]}',
                      headers=auth_headers).status_code == 404
    assert client.get('/api/document-templates', headers=auth_headers).get_json() == []
    with app.app_context():
        # Still there: a pack may record having been rendered from it.
        assert db_session.query(DocumentTemplate).count() == 1


def test_missing_templates_are_404(client, auth_headers):
    for call in (
            lambda: client.get('/api/document-templates/4242', headers=auth_headers),
            lambda: client.put('/api/document-templates/4242', json=_tree(),
                               headers=auth_headers),
            lambda: client.post('/api/document-templates/4242/versions',
                                headers=auth_headers),
            lambda: client.post('/api/document-templates/4242/publish',
                                headers=auth_headers),
            lambda: client.delete('/api/document-templates/4242', headers=auth_headers)):
        assert call().status_code == 404


def test_a_viewer_may_read_but_not_write(client, auth_headers, viewer_headers):
    created = _create(client, auth_headers).get_json()
    assert client.get('/api/document-templates', headers=viewer_headers).status_code == 200
    assert client.post('/api/document-templates', json=_tree(code='other'),
                       headers=viewer_headers).status_code == 403
    assert client.put(f'/api/document-templates/{created["id"]}', json=created,
                      headers=viewer_headers).status_code == 403


def test_an_editor_may_save_but_not_publish_or_delete(client, auth_headers, editor_headers):
    created = _create(client, editor_headers)
    assert created.status_code == 201
    template_id = created.get_json()['id']
    assert client.put(f'/api/document-templates/{template_id}',
                      json=created.get_json(), headers=editor_headers).status_code == 200
    assert client.post(f'/api/document-templates/{template_id}/publish',
                       headers=editor_headers).status_code == 403
    assert client.delete(f'/api/document-templates/{template_id}',
                         headers=editor_headers).status_code == 403


def test_authentication_is_required(client):
    assert client.get('/api/document-templates').status_code == 401


def test_a_saved_tree_renders(app, client, auth_headers):
    """The end of the round trip: what the API stored is what the renderer
    draws. Without this the API could happily persist a tree the PDF path
    chokes on, and the failure would surface in a client document."""
    from renderers.bindings import resolve_tree
    from renderers.html_pdf_renderer import render_template_html

    created = _create(client, auth_headers).get_json()
    fetched = client.get(f'/api/document-templates/{created["id"]}',
                         headers=auth_headers).get_json()

    tree = resolve_tree(fetched['sections'], {
        'system': {'client_name': 'Meridian Endowment', 'report_title': 'Q3 2026'},
    })
    html = render_template_html(tree)
    assert 'Performance' in html
    assert 'Meridian Endowment' in html
    # The style token reached the page. Until E3 it was stored, carried
    # through the tree, and then silently ignored by the renderer.
    assert 'st-heading-1' in html
    assert '.st-heading-1 {' in html
    assert 'color-primary' in html
