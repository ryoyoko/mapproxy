from __future__ import division
import yaml
from cStringIO import StringIO
from mapproxy.srs import SRS
from mapproxy.config.loader import (
    ProxyConfiguration,
    load_services,
    merge_dict,
    ConfigurationError,
)
from mapproxy.cache.tile import TileManager
from mapproxy.test.helper import TempFile
from mapproxy.test.unit.test_grid import assert_almost_equal_bbox
from nose.tools import eq_
from nose.plugins.skip import SkipTest

class TestLayerConfiguration(object):
    def _test_conf(self, yaml_part):
        base = {'sources': {'s': {'type': 'wms', 'req': {'url': ''}}}}
        base.update(yaml.load(yaml_part))
        return base
    
    def test_legacy_ordered(self):
        conf = self._test_conf('''
            layers:
              - one:
                 title: Layer One
                 sources: [s]
              - two:
                 title: Layer Two
                 sources: [s]
              - three:
                 title: Layer Three
                 sources: [s]
        ''')
        conf = ProxyConfiguration(conf)
        root = conf.wms_root_layer.wms_layer()
        
        # no root layer defined
        eq_(root.title, None)
        eq_(root.name, None)
        layers = root.child_layers()
        
        # names are in order
        eq_(layers.keys(), ['one', 'two', 'three'])
        
        eq_(len(layers), 3)
        eq_(layers['one'].title, 'Layer One')
        eq_(layers['two'].title, 'Layer Two')
        eq_(layers['three'].title, 'Layer Three')
        
        layers_conf = conf.layers
        eq_(len(layers_conf), 3)

    def test_legacy_unordered(self):
        conf = self._test_conf('''
            layers:
              one:
                title: Layer One
                sources: [s]
              two:
                title: Layer Two
                sources: [s]
              three:
                title: Layer Three
                sources: [s]
        ''')
        conf = ProxyConfiguration(conf)
        root = conf.wms_root_layer.wms_layer()
        
        # no root layer defined
        eq_(root.title, None)
        eq_(root.name, None)
        layers = root.child_layers()
        
        # names might not be in order
        # layers.keys() != ['one', 'two', 'three']
        
        eq_(len(layers), 3)
        eq_(layers['one'].title, 'Layer One')
        eq_(layers['two'].title, 'Layer Two')
        eq_(layers['three'].title, 'Layer Three')

    def test_with_root(self):
        conf = self._test_conf('''
            layers:
              name: root
              title: Root Layer
              layers:
                - name: one
                  title: Layer One
                  sources: [s]
                - name: two
                  title: Layer Two
                  sources: [s]
        ''')
        conf = ProxyConfiguration(conf)
        root = conf.wms_root_layer.wms_layer()
        
        eq_(root.title, 'Root Layer')
        eq_(root.name, 'root')
        layers = root.child_layers()
        
        # names are in order
        eq_(layers.keys(), ['root', 'one', 'two'])
        
        eq_(len(layers), 3)
        eq_(layers['root'].title, 'Root Layer')
        eq_(layers['one'].title, 'Layer One')
        eq_(layers['two'].title, 'Layer Two')
        
        layers_conf = conf.layers
        eq_(len(layers_conf), 2)
    
    def test_with_unnamed_root(self):
        conf = self._test_conf('''
            layers:
              title: Root Layer
              layers:
                - name: one
                  title: Layer One
                  sources: [s]
                - name: two
                  title: Layer Two
                  sources: [s]
        ''')
        conf = ProxyConfiguration(conf)
        root = conf.wms_root_layer.wms_layer()
        
        eq_(root.title, 'Root Layer')
        eq_(root.name, None)

        layers = root.child_layers()
        # names are in order
        eq_(layers.keys(), ['one', 'two'])
    
    def test_without_root(self):
        conf = self._test_conf('''
            layers:
                - name: one
                  title: Layer One
                  sources: [s]
                - name: two
                  title: Layer Two
                  sources: [s]
        ''')
        conf = ProxyConfiguration(conf)
        root = conf.wms_root_layer.wms_layer()
        
        eq_(root.title, None)
        eq_(root.name, None)

        layers = root.child_layers()
        # names are in order
        eq_(layers.keys(), ['one', 'two'])
    
    def test_hierarchy(self):
        conf = self._test_conf('''
            layers:
              title: Root Layer
              layers:
                - name: one
                  title: Layer One
                  layers:
                    - name: onea
                      title: Layer One A
                      sources: [s]
                    - name: oneb
                      title: Layer One B
                      layers:
                        - name: oneba
                          title: Layer One B A
                          sources: [s]
                        - name: onebb
                          title: Layer One B B
                          sources: [s]
                - name: two
                  title: Layer Two
                  sources: [s]
        ''')
        conf = ProxyConfiguration(conf)
        root = conf.wms_root_layer.wms_layer()
        
        eq_(root.title, 'Root Layer')
        eq_(root.name, None)

        layers = root.child_layers()
        # names are in order
        eq_(layers.keys(), ['one', 'onea', 'oneb', 'oneba', 'onebb', 'two'])
        
        layers_conf = conf.layers
        eq_(len(layers_conf), 4)
        eq_(layers_conf.keys(), ['onea', 'oneba', 'onebb', 'two'])
        eq_(layers_conf['onea'].conf['title'], 'Layer One A')
        eq_(layers_conf['onea'].conf['name'], 'onea')
        eq_(layers_conf['onea'].conf['sources'], ['s'])
    
    def test_hierarchy_root_is_list(self):
        conf = self._test_conf('''
            layers:
              - title: Root Layer
                layers:
                    - name: one
                      title: Layer One
                      sources: [s]
                    - name: two
                      title: Layer Two
                      sources: [s]
        ''')
        conf = ProxyConfiguration(conf)
        root = conf.wms_root_layer.wms_layer()
        
        eq_(root.title, 'Root Layer')
        eq_(root.name, None)

        layers = root.child_layers()
        # names are in order
        eq_(layers.keys(), ['one', 'two'])
    
    def test_without_sources_or_layers(self):
        conf = self._test_conf('''
            layers:
              title: Root Layer
              layers:
                - name: one
                  title: Layer One
        ''')
        conf = ProxyConfiguration(conf)
        try:
            conf.wms_root_layer.wms_layer()
        except ValueError:
            pass
        else:
            assert False, 'expected ValueError'
        

class TestGridConfiguration(object):
    def test_default_grids(self):
        conf = {}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['GLOBAL_MERCATOR'].tile_grid()
        eq_(grid.srs, SRS(900913))
    
        grid = conf.grids['GLOBAL_GEODETIC'].tile_grid()
        eq_(grid.srs, SRS(4326))
    
    
    def test_simple(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55]}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid()
        eq_(grid.srs, SRS(4326))

    def test_with_base(self):
        conf = {'grids': {
            'base_grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55]},
            'grid': {'base': 'base_grid'}
        }}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid()
        eq_(grid.srs, SRS(4326))

    def test_with_num_levels(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55], 'num_levels': 8}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid()
        eq_(len(grid.resolutions), 8)
    
    def test_with_bbox_srs(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:25832', 'bbox': [5, 50, 10, 55], 'bbox_srs': 'EPSG:4326'}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid()
        assert_almost_equal_bbox([213372, 5538660, 571666, 6102110], grid.bbox, -3)
    
    def test_with_min_res(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55], 'min_res': 0.0390625}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid()
        assert_almost_equal_bbox([5, 50, 10, 55], grid.bbox, 2)
        eq_(grid.resolution(0), 0.0390625)
        eq_(grid.resolution(1), 0.01953125)
    
    def test_with_max_res(self):
        conf = {'grids': {'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55], 'max_res': 0.0048828125}}}
        conf = ProxyConfiguration(conf)
        grid = conf.grids['grid'].tile_grid()
        assert_almost_equal_bbox([5, 50, 10, 55], grid.bbox, 2)
        eq_(grid.resolution(0), 0.01953125)
        eq_(grid.resolution(1), 0.01953125/2)
    
class TestWMSSourceConfiguration(object):
    def test_simple_grid(self):
        conf_dict = {
            'grids': {
                'grid': {'srs': 'EPSG:4326', 'bbox': [5, 50, 10, 55]},
            },
            'sources': {
                'osm': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://localhost/service?',
                        'layers': 'base',
                    },
                },
            },
            'caches': {
                'osm': {
                    'sources': ['osm'],
                    'grids': ['grid'],
                }
            }
        }
        
        conf = ProxyConfiguration(conf_dict)
        
        caches = conf.caches['osm'].caches()
        eq_(len(caches), 1)
        grid, extent, manager = caches[0]
        
        eq_(grid.srs, SRS(4326))
        eq_(grid.bbox, (5.0, 50.0, 10.0, 55.0))
        
        assert isinstance(manager, TileManager)
    
    def check_source_layers(self, conf_dict, layers):
        conf = ProxyConfiguration(conf_dict)
        caches = conf.caches['osm'].caches()
        eq_(len(caches), 1)
        grid, extent, manager = caches[0]
        source_layers = manager.sources[0].client.request_template.params.layers
        eq_(source_layers, layers)
        
    def test_tagged_source(self):
        conf_dict = {
            'sources': {
                'osm': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://localhost/service?',
                    },
                },
            },
            'caches': {
                'osm': {
                    'sources': ['osm:base,roads'],
                    'grids': ['GLOBAL_MERCATOR'],
                }
            }
        }
        self.check_source_layers(conf_dict, ['base', 'roads'])

    def test_tagged_source_with_layers(self):
        conf_dict = {
            'sources': {
                'osm': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://localhost/service?',
                        'layers': 'base,roads,poi'
                    },
                },
            },
            'caches': {
                'osm': {
                    'sources': ['osm:base,roads'],
                    'grids': ['GLOBAL_MERCATOR'],
                }
            }
        }
        self.check_source_layers(conf_dict, ['base', 'roads'])

    def test_tagged_source_with_layers_missing(self):
        conf_dict = {
            'sources': {
                'osm': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://localhost/service?',
                        'layers': 'base,poi'
                    },
                },
            },
            'caches': {
                'osm': {
                    'sources': ['osm:base,roads'],
                    'grids': ['GLOBAL_MERCATOR'],
                }
            }
        }
        conf = ProxyConfiguration(conf_dict)
        try:
            conf.caches['osm'].caches()
        except ConfigurationError, ex:
            assert 'base,roads' in ex.args[0]
            assert 'base,poi' in ex.args[0]
        else:
            assert False, 'expected ConfigurationError'
    
    def test_tagged_source_on_non_wms_source(self):
        conf_dict = {
            'sources': {
                'osm': {
                    'type': 'tile',
                    'url': 'http://example.org/'
                },
            },
            'caches': {
                'osm': {
                    'sources': ['osm:base,roads'],
                    'grids': ['GLOBAL_MERCATOR'],
                }
            }
        }
        conf = ProxyConfiguration(conf_dict)
        try:
            conf.caches['osm'].caches()
        except ConfigurationError, ex:
            assert 'osm:base,roads' in ex.args[0]
        else:
            assert False, 'expected ConfigurationError'
    
    
    def test_layer_tagged_source(self):
        conf_dict = {
            'layers': [
                {
                    'name': 'osm',
                    'title': 'OSM',
                    'sources': ['osm:base,roads']
                }
            ],
            'sources': {
                'osm': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://localhost/service?',
                    },
                },
            },
        }
        conf = ProxyConfiguration(conf_dict)
        wms_layer = conf.layers['osm'].wms_layer()
        layers = wms_layer.map_layers[0].client.request_template.params.layers
        eq_(layers, ['base', 'roads'])
    
    def test_https_source_insecure(self):
        conf_dict = {
            'sources': {
                'osm': {
                    'type': 'wms',
                    'http':{'ssl_no_cert_checks': True},
                    'req': {
                        'url': 'https://foo:bar@localhost/service?',
                        'layers': 'base',
                    },
                },
            },
        }
        
        conf = ProxyConfiguration(conf_dict)
        try:
            conf.sources['osm'].source({'format': 'image/png'})
        except ImportError:
            raise SkipTest('no ssl support')
        
    
class TestConfLoading(object):
    yaml_string = """
services:
  wms:

layers:
  - name: osm
    title: OSM
    sources: [osm]

sources:
  osm:
    type: wms
    supported_srs: ['EPSG:31467']
    req: 
        url: http://foo
        layers: base
"""
    
    def test_loading(self):
        with TempFile() as f:
            open(f, 'w').write(self.yaml_string)
            services = load_services(f)
        assert 'wms' in services

    def test_loading_broken_yaml(self):
        with TempFile() as f:
            open(f, 'w').write('\tbroken:foo')
            try:
                services = load_services(f)
            except ConfigurationError:
                pass
            else:
                assert False, 'expected configuration error'


class TestConfMerger(object):
    def test_empty_base(self):
        a = {'a': 1, 'b': [12, 13]}
        b = {}
        m = merge_dict(a, b)
        eq_(a, m)
    
    def test_empty_conf(self):
        a = {}
        b = {'a': 1, 'b': [12, 13]}
        m = merge_dict(a, b)
        eq_(b, m)
    
    def test_differ(self):
        a = {'a': 12}
        b = {'b': 42}
        m = merge_dict(a, b)
        eq_({'a': 12, 'b': 42}, m)
    
    def test_recursive(self):
        a = {'a': {'aa': 12, 'a':{'aaa': 100}}}
        b = {'a': {'aa': 11, 'ab': 13, 'a':{'aaa': 101, 'aab': 101}}}
        m = merge_dict(a, b)
        eq_({'a': {'aa': 12, 'ab': 13, 'a':{'aaa': 100, 'aab': 101}}}, m)
        