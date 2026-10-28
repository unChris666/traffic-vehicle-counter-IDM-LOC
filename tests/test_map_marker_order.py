"""Real Folium render: marker groups must exist before LayerControl references."""
import importlib.util,unittest

@unittest.skipUnless(importlib.util.find_spec('folium'),'Run Area presentation environment')
class MarkerOrderTests(unittest.TestCase):
    def test_every_marker_survives_grouping_and_is_defined_before_control(self):
        import folium
        from folium.plugins import MarkerCluster
        from traffic_location.location.area.outputs.map import consolidate
        m=folium.Map(location=[-6,106],tiles=None)
        layers=[]
        for name,cluster in [('Calon toko — pin putih',False),('POI Pasar',True),('Kompetitor primer — pin',True),('Indomaret — pin',True)]:
            layer=(MarkerCluster(name=name) if cluster else folium.FeatureGroup(name=name)).add_to(m)
            folium.Marker([-6,106],tooltip=name).add_to(layer);layers.append(layer)
        control=folium.LayerControl().add_to(m)
        consolidate(m)
        html=m.get_root().render()
        control_position=html.index('var '+control.get_name())
        for layer in layers:
            self.assertIn('var '+layer.get_name(),html)
            self.assertLess(html.index('var '+layer.get_name()),control_position)
            group=layer._parent
            self.assertLess(html.index('var '+group.get_name()),control_position)
            self.assertEqual(sum(isinstance(c,folium.Marker) for c in layer._children.values()),1)
        # Repeated saves must not create nested duplicate groups or lose points.
        parents=[layer._parent for layer in layers]
        consolidate(m)
        self.assertEqual(len([v for v in m._children.values() if isinstance(v,folium.LayerControl)]),1)
        self.assertEqual([layer._parent for layer in layers],parents)
        self.assertEqual(sum(isinstance(c,folium.Marker) for layer in layers for c in layer._children.values()),4)
