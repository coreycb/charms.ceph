# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import unittest

from mock import patch

import ceph.broker

from mock import call


class CephBrokerTestCase(unittest.TestCase):
    def setUp(self):
        super(CephBrokerTestCase, self).setUp()

    @patch.object(ceph.broker, 'check_call')
    def test_update_service_permission(self, _check_call):
        service_obj = {
            'group_names': {'rwx': ['images']},
            'groups': {'images': {'pools': ['cinder'], 'services': ['nova']}}
        }
        ceph.broker.update_service_permissions(service='nova',
                                               service_obj=service_obj)
        _check_call.assert_called_with(['ceph', 'auth', 'caps',
                                        'client.nova', 'mon', 'allow r', 'osd',
                                        'allow rwx pool=cinder'])

    @patch.object(ceph.broker, 'check_call')
    @patch.object(ceph.broker, 'get_service_groups')
    @patch.object(ceph.broker, 'monitor_key_set')
    @patch.object(ceph.broker, 'monitor_key_get')
    def test_add_pool_to_existing_group_with_services(self,
                                                      _monitor_key_get,
                                                      _monitor_key_set,
                                                      _get_service_groups,
                                                      _check_call):
        _monitor_key_get.return_value = '{"pools": ["glance"],'\
            ' "services": ["nova"]}'
        service = {
            'group_names': {'rwx': ['images']},
            'groups': {'images': {'pools': [
                'glance', 'cinder'
            ], 'services': ['nova']}}
        }
        _get_service_groups.return_value = service
        ceph.broker.add_pool_to_group(
            pool="cinder",
            group="images"
        )
        _monitor_key_set.assert_called_with(
            key='cephx.groups.images',
            service='admin',
            value=json.dumps({"pools": ["glance", "cinder"],
                              "services": ["nova"]}))
        _check_call.assert_called_with([
            'ceph', 'auth', 'caps',
            'client.nova', 'mon', 'allow r', 'osd',
            'allow rwx pool=glance, allow rwx pool=cinder'])

    @patch.object(ceph.broker, 'monitor_key_set')
    @patch.object(ceph.broker, 'monitor_key_get')
    def test_add_pool_to_existing_group(self,
                                        _monitor_key_get,
                                        _monitor_key_set):
        _monitor_key_get.return_value = '{"pools": ["glance"], "services": []}'
        ceph.broker.add_pool_to_group(
            pool="cinder",
            group="images"
        )
        _monitor_key_set.assert_called_with(
            key='cephx.groups.images',
            service='admin',
            value=json.dumps({"pools": ["glance", "cinder"], "services": []}))

    @patch.object(ceph.broker, 'monitor_key_set')
    @patch.object(ceph.broker, 'monitor_key_get')
    def test_add_pool_to_new_group(self,
                                   _monitor_key_get,
                                   _monitor_key_set):
        _monitor_key_get.return_value = '{"pools": [], "services": []}'
        ceph.broker.add_pool_to_group(
            pool="glance",
            group="images"
        )
        _monitor_key_set.assert_called_with(
            key='cephx.groups.images',
            service='admin',
            value=json.dumps({"pools": ["glance"], "services": []}))

    def test_pool_permission_list_for_service(self):
        service = {
            'group_names': {'rwx': ['images']},
            'groups': {'images': {'pools': ['glance'], 'services': ['nova']}}
        }
        result = ceph.broker.pool_permission_list_for_service(service)
        self.assertEqual(result, ['mon',
                                  'allow r',
                                  'osd',
                                  'allow rwx pool=glance'])

    def test_pool_permission_list_for_service_multi(self):
        service = {
            'group_names': {'rwx': ['images', 'group1'], 'r': ['group2']},
            'groups': {
                'images': {
                    'pools': ['glance'],
                    'services': ['nova']},
                'group1': {
                    'pools': ['p1'],
                    'services': ['svc1']},
                'group2': {
                    'pools': ['p2'],
                    'services': ['svc2']}}
        }
        result = ceph.broker.pool_permission_list_for_service(service)
        self.assertEqual(
            result,
            [
                'mon',
                'allow r',
                'osd',
                'allow r pool=p2, allow rwx pool=glance, allow rwx pool=p1'])

    @patch.object(ceph.broker, 'monitor_key_set')
    def test_save_service(self, _monitor_key_set):
        service = {
            'group_names': {'rwx': 'images'},
            'groups': {'images': {'pools': ['glance'], 'services': ['nova']}}
        }
        ceph.broker.save_service(service=service, service_name='nova')
        _monitor_key_set.assert_called_with(
            value='{"groups": {}, "group_names": {"rwx": "images"}}',
            key='cephx.services.nova',
            service='admin')

    @patch.object(ceph.broker, 'monitor_key_get')
    def test_get_service_groups_empty(self, _monitor_key_get):
        _monitor_key_get.return_value = None
        service = ceph.broker.get_service_groups('nova')
        _monitor_key_get.assert_called_with(
            key='cephx.services.nova',
            service='admin'
        )
        self.assertEqual(service, {'group_names': {}, 'groups': {}})

    @patch.object(ceph.broker, 'monitor_key_get')
    def test_get_service_groups_empty_str(self, _monitor_key_get):
        _monitor_key_get.return_value = ''
        service = ceph.broker.get_service_groups('nova')
        _monitor_key_get.assert_called_with(
            key='cephx.services.nova',
            service='admin'
        )
        self.assertEqual(service, {'group_names': {}, 'groups': {}})

    @patch.object(ceph.broker, 'get_group')
    @patch.object(ceph.broker, 'monitor_key_get')
    def test_get_service_groups(self, _monitor_key_get, _get_group):
        _monitor_key_get.return_value = '{"group_names": {"rwx": ["images"]}' \
            ',"groups": {}}'
        _get_group.return_value = {
            'pools': ["glance"],
            'services': ['nova']
        }
        service = ceph.broker.get_service_groups('nova')
        _monitor_key_get.assert_called_with(
            key='cephx.services.nova',
            service='admin'
        )
        self.assertEqual(service, {
            'group_names': {'rwx': ['images']},
            'groups': {'images': {'pools': ['glance'], 'services': ['nova']}}
        })

    @patch.object(ceph.broker, 'monitor_key_set')
    def test_save_group(self, _monitor_key_set):
        group = {
            'pools': ["glance"],
            'services': []
        }
        ceph.broker.save_group(group=group, group_name='images')
        _monitor_key_set.assert_called_with(
            key='cephx.groups.images',
            service='admin',
            value=json.dumps(group))

    @patch.object(ceph.broker, 'monitor_key_get')
    def test_get_group_empty_str(self, _monitor_key_get):
        _monitor_key_get.return_value = ''
        group = ceph.broker.get_group('images')
        self.assertEqual(group, {
            'pools': [],
            'services': []
        })

    @patch.object(ceph.broker, 'monitor_key_get')
    def test_get_group_empty(self, _monitor_key_get):
        _monitor_key_get.return_value = None
        group = ceph.broker.get_group('images')
        self.assertEqual(group, {
            'pools': [],
            'services': []
        })

    @patch.object(ceph.broker, 'monitor_key_get')
    def test_get_group(self, _monitor_key_get):
        _monitor_key_get.return_value = '{"pools": ["glance"], "services": []}'
        group = ceph.broker.get_group('images')
        self.assertEqual(group, {
            'pools': ["glance"],
            'services': []
        })

    @patch.object(ceph.broker, 'log')
    def test_process_requests_noop(self, mock_log):
        req = json.dumps({'api-version': 1, 'ops': []})
        rc = ceph.broker.process_requests(req)
        self.assertEqual(json.loads(rc), {'exit-code': 0})

    @patch.object(ceph.broker, 'log')
    def test_process_requests_missing_api_version(self, mock_log):
        req = json.dumps({'ops': []})
        rc = ceph.broker.process_requests(req)
        self.assertEqual(json.loads(rc), {
            'exit-code': 1,
            'stderr': 'Missing or invalid api version (None)'})

    @patch.object(ceph.broker, 'log')
    def test_process_requests_invalid_api_version(self, mock_log):
        req = json.dumps({'api-version': 2, 'ops': []})
        rc = ceph.broker.process_requests(req)
        self.assertEqual(json.loads(rc),
                         {'exit-code': 1,
                          'stderr': 'Missing or invalid api version (2)'})

    @patch.object(ceph.broker, 'log')
    def test_process_requests_invalid(self, mock_log):
        reqs = json.dumps({'api-version': 1, 'ops': [{'op': 'invalid_op'}]})
        rc = ceph.broker.process_requests(reqs)
        self.assertEqual(json.loads(rc),
                         {'exit-code': 1,
                          'stderr': "Unknown operation 'invalid_op'"})

    @patch.object(ceph.broker, 'ReplicatedPool')
    @patch.object(ceph.broker, 'pool_exists')
    @patch.object(ceph.broker, 'log')
    def test_process_requests_create_pool_w_pg_num(self, mock_log,
                                                   mock_pool_exists,
                                                   mock_replicated_pool):
        mock_pool_exists.return_value = False
        reqs = json.dumps({'api-version': 1,
                           'ops': [{
                               'op': 'create-pool',
                               'name': 'foo',
                               'replicas': 3,
                               'pg_num': 100}]})
        rc = ceph.broker.process_requests(reqs)
        mock_pool_exists.assert_called_with(service='admin', name='foo')
        mock_replicated_pool.assert_called_with(service='admin', name='foo',
                                                replicas=3, pg_num=100)
        self.assertEqual(json.loads(rc), {'exit-code': 0})

    @patch.object(ceph.broker, 'ReplicatedPool')
    @patch.object(ceph.broker, 'pool_exists')
    @patch.object(ceph.broker, 'log')
    @patch.object(ceph.broker, 'add_pool_to_group')
    def test_process_requests_create_pool_w_group(self, add_pool_to_group,
                                                  mock_log, mock_pool_exists,
                                                  mock_replicated_pool):
        mock_pool_exists.return_value = False
        reqs = json.dumps({'api-version': 1,
                           'ops': [{
                               'op': 'create-pool',
                               'name': 'foo',
                               'replicas': 3,
                               'group': 'image'}]})
        rc = ceph.broker.process_requests(reqs)
        add_pool_to_group.assert_called_with(group='image',
                                             pool='foo',
                                             namespace=None)
        mock_pool_exists.assert_called_with(service='admin', name='foo')
        mock_replicated_pool.assert_called_with(service='admin', name='foo',
                                                replicas=3)
        self.assertEqual(json.loads(rc), {'exit-code': 0})

    @patch.object(ceph.broker, 'ReplicatedPool')
    @patch.object(ceph.broker, 'pool_exists')
    @patch.object(ceph.broker, 'log')
    def test_process_requests_create_pool_exists(self, mock_log,
                                                 mock_pool_exists,
                                                 mock_replicated_pool):
        mock_pool_exists.return_value = True
        reqs = json.dumps({'api-version': 1,
                           'ops': [{'op': 'create-pool',
                                    'name': 'foo',
                                    'replicas': 3}]})
        rc = ceph.broker.process_requests(reqs)
        mock_pool_exists.assert_called_with(service='admin',
                                            name='foo')
        self.assertFalse(mock_replicated_pool.create.called)
        self.assertEqual(json.loads(rc), {'exit-code': 0})

    @patch.object(ceph.broker, 'ReplicatedPool')
    @patch.object(ceph.broker, 'pool_exists')
    @patch.object(ceph.broker, 'log')
    def test_process_requests_create_pool_rid(self, mock_log,
                                              mock_pool_exists,
                                              mock_replicated_pool):
        mock_pool_exists.return_value = False
        reqs = json.dumps({'api-version': 1,
                           'request-id': '1ef5aede',
                           'ops': [{
                               'op': 'create-pool',
                               'name': 'foo',
                               'replicas': 3}]})
        rc = ceph.broker.process_requests(reqs)
        mock_pool_exists.assert_called_with(service='admin', name='foo')
        mock_replicated_pool.assert_called_with(service='admin',
                                                name='foo',
                                                replicas=3)
        self.assertEqual(json.loads(rc)['exit-code'], 0)
        self.assertEqual(json.loads(rc)['request-id'], '1ef5aede')

    @patch.object(ceph.broker, 'get_cephfs')
    @patch.object(ceph.broker, 'check_output')
    @patch.object(ceph.broker, 'pool_exists')
    @patch.object(ceph.broker, 'log')
    def test_process_requests_create_cephfs(self,
                                            mock_log,
                                            mock_pool_exists,
                                            check_output,
                                            get_cephfs):
        get_cephfs.return_value = []
        mock_pool_exists.return_value = True
        reqs = json.dumps({'api-version': 1,
                           'request-id': '1ef5aede',
                           'ops': [{
                               'op': 'create-cephfs',
                               'mds_name': 'foo',
                               'data_pool': 'data',
                               'metadata_pool': 'metadata',
                           }]})
        rc = ceph.broker.process_requests(reqs)
        mock_pool_exists.assert_has_calls(
            [
                call(service='admin', name='data'),
                call(service='admin', name='metadata'),
            ])
        check_output.assert_called_with(["ceph",
                                         '--id', 'admin',
                                         "fs", "new", 'foo',
                                         'metadata',
                                         'data'])

        self.assertEqual(json.loads(rc)['exit-code'], 0)
        self.assertEqual(json.loads(rc)['request-id'], '1ef5aede')

    @patch.object(ceph.broker, 'check_output')
    @patch.object(ceph.broker, 'get_osd_weight')
    @patch.object(ceph.broker, 'log')
    @patch('ceph.crush_utils.Crushmap.load_crushmap')
    @patch('ceph.crush_utils.Crushmap.ensure_bucket_is_present')
    def test_process_requests_move_osd(self,
                                       mock_ensure_bucket_is_present,
                                       mock_load_crushmap,
                                       mock_log,
                                       mock_get_osd_weight,
                                       mock_check_output):
        mock_load_crushmap.return_value = ""
        mock_ensure_bucket_is_present.return_value = None
        mock_get_osd_weight.return_value = 1
        reqs = json.dumps({'api-version': 1,
                           'request-id': '1ef5aede',
                           'ops': [{
                               'op': 'move-osd-to-bucket',
                               'osd': 'osd.0',
                               'bucket': 'test'
                           }]})
        rc = ceph.broker.process_requests(reqs)
        self.assertEqual(json.loads(rc)['exit-code'], 0)
        self.assertEqual(json.loads(rc)['request-id'], '1ef5aede')
        mock_check_output.assert_called_with(["ceph",
                                              '--id', 'admin',
                                              "osd", "crush", "set",
                                              "osd.0", "1", "root=test"])

    @patch.object(ceph.broker, 'log')
    def test_process_requests_invalid_api_rid(self, mock_log):
        reqs = json.dumps({'api-version': 0, 'request-id': '1ef5aede',
                           'ops': [{'op': 'create-pool'}]})
        rc = ceph.broker.process_requests(reqs)
        self.assertEqual(json.loads(rc)['exit-code'], 1)
        self.assertEqual(json.loads(rc)['stderr'],
                         "Missing or invalid api version (0)")
        self.assertEqual(json.loads(rc)['request-id'], '1ef5aede')

    @patch.object(ceph.broker, 'handle_add_permissions_to_key')
    @patch.object(ceph.broker, 'log')
    def test_process_requests_add_perms(self, mock_log,
                                        mock_handle_add_permissions_to_key):
        request = {
            "api-version": 1,
            "request-id": "0155c14b",
            "ops": [
                {
                    "namespace": None,
                    "group-permission": "rwx",
                    "group": "images",
                    "name": "glance",
                    "op": "add-permissions-to-key"
                }
            ]
        }
        reqs = json.dumps(request)
        rc = ceph.broker.process_requests(reqs)
        mock_handle_add_permissions_to_key.assert_called_once_with(
            request={
                u'namespace': None,
                u'group-permission': u'rwx',
                u'group': u'images',
                u'name': u'glance',
                u'op': u'add-permissions-to-key'},
            service='admin')
        self.assertEqual(
            json.loads(rc),
            {'exit-code': 0, u'request-id': u'0155c14b'})

    @patch.object(ceph.broker, 'handle_add_permissions_to_key')
    @patch.object(ceph.broker, 'log')
    def test_process_requests_add_multi_perms(self, mock_log,
                                              mock_handle_add_perms_to_key):
        request = {
            "api-version": 1,
            "request-id": "0155c14b",
            "ops": [
                {
                    "namespace": None,
                    "group-permission": "rwx",
                    "group": "images",
                    "name": "glance",
                    "op": "add-permissions-to-key"
                },
                {
                    "namespace": None,
                    "group-permission": "r",
                    "group": "volumes",
                    "name": "cinder",
                    "op": "add-permissions-to-key"
                }
            ]
        }
        reqs = json.dumps(request)
        rc = ceph.broker.process_requests(reqs)
        call1 = call(
            request={
                u'namespace': None,
                u'group-permission': u'rwx',
                u'group': u'images',
                u'name': u'glance',
                u'op': u'add-permissions-to-key'},
            service='admin')
        call2 = call(
            request={
                u'namespace': None,
                u'group-permission': u'r',
                u'group': u'volumes',
                u'name': u'cinder',
                u'op': u'add-permissions-to-key'},
            service='admin')
        mock_handle_add_perms_to_key.assert_has_calls([call1, call2])
        self.assertEqual(
            json.loads(rc),
            {'exit-code': 0, u'request-id': u'0155c14b'})

    @patch.object(ceph.broker, 'save_service')
    @patch.object(ceph.broker, 'save_group')
    @patch.object(ceph.broker, 'monitor_key_get')
    @patch.object(ceph.broker, 'update_service_permissions')
    def test_handle_add_permissions_to_key(self,
                                           mock_update_service_permissions,
                                           mock_monitor_key_get,
                                           mock_save_group,
                                           mock_save_service):
        mkey = {
            'cephx.services.glance': ('{"groups": {}, '
                                      '"group_names": {"rwx": ["images"]}}'),
            'cephx.groups.images': ('{"services": ["glance", "cinder-ceph", '
                                    '"nova-compute"], "pools": ["glance"]}')}
        mock_monitor_key_get.side_effect = lambda service, key: mkey[key]
        expect_service_name = u'glance'
        expected_group = {
            u'services': [
                u'glance',
                u'cinder-ceph',
                u'nova-compute'],
            u'pools': [u'glance']}
        expect_service_obj = {
            u'groups': {
                u'images': expected_group},
            u'group_names': {
                u'rwx': [u'images']}}
        expect_group_namespace = None
        ceph.broker.handle_add_permissions_to_key(
            request={
                u'namespace': None,
                u'group-permission': u'rwx',
                u'group': u'images',
                u'name': u'glance',
                u'op': u'add-permissions-to-key'},
            service='admin')
        mock_save_group.assert_called_once_with(
            group=expected_group,
            group_name='images')
        mock_save_service.assert_called_once_with(
            service=expect_service_obj,
            service_name=expect_service_name)
        mock_update_service_permissions.assert_called_once_with(
            expect_service_name,
            expect_service_obj,
            expect_group_namespace)
