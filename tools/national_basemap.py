"""Build a national OSM vector PMTiles archive from the pinned private GCS PBF."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess

PBF_REF={'object':'sources/osm/indonesia/bb1b60f7dfdbb1f19d33fa1ffb0c546f7e75928126ac3a2c004839a3ff2003bc/indonesia.osm.pbf',
    'generation':1792937275821365,'bytes':1739881462,
    'sha256':'bb1b60f7dfdbb1f19d33fa1ffb0c546f7e75928126ac3a2c004839a3ff2003bc'}
PLANETILER_URL='https://github.com/onthegomap/planetiler/releases/download/v0.10.2/planetiler.jar'
PLANETILER_SHA='f310bd0413e2e4512b27f4046d418664e8e1d3bf31603c2a70e23de06c167e4d'
PROFILE_VERSION='indonesia-osm-basic-v1-z14'
MAXZOOM=14
JAVA_HEAP_GB=8
PROFILE_SOURCE=r'''import com.onthegomap.planetiler.FeatureCollector;
import com.onthegomap.planetiler.Planetiler;
import com.onthegomap.planetiler.Profile;
import com.onthegomap.planetiler.config.Arguments;
import com.onthegomap.planetiler.reader.SourceFeature;
import java.nio.file.Path;

public class IndonesiaBasemap implements Profile {
  public String name() { return "Indonesia OSM Basic"; }
  public String description() { return "OSM vector basemap; mapped features only; analytic counting is independent"; }
  public boolean isOverlay() { return false; }
  public String attribution() { return "© OpenStreetMap contributors, ODbL"; }
  private static void named(FeatureCollector.Feature feature, SourceFeature source) {
    if (source.getTag("name") != null) feature.setAttr("name",source.getTag("name"));
  }
  public void processFeature(SourceFeature source, FeatureCollector features) {
    if (source.canBeLine() && source.hasTag("highway")) {
      String road=String.valueOf(source.getTag("highway"));
      int min=road.matches("^(motorway|trunk)(_link)?$")?5:
        road.matches("^(primary|secondary)(_link)?$")?8:
        road.matches("^tertiary(_link)?$")?10:
        road.matches("^(residential|unclassified|living_street)$")?12:13;
      named(features.line("roads").setAttr("class",road).setZoomRange(min,14),source);
    }
    if (source.canBeLine() && source.hasTag("natural","coastline"))
      features.line("coastline").setZoomRange(0,14);
    if (source.canBeLine() && source.hasTag("waterway"))
      named(features.line("waterways").setAttr("class",source.getTag("waterway")).setZoomRange(9,14),source);
    if (source.canBeLine() && source.hasTag("boundary","administrative"))
      features.line("boundaries").setAttr("class",source.getTag("admin_level")).setZoomRange(5,14);
    if (source.canBePolygon()) {
      if (source.hasTag("building") && !source.hasTag("building","no"))
        named(features.polygon("buildings").setAttr("class",source.getTag("building"))
          .setZoomRange(14,14).setMinPixelSizeAtAllZooms(0).setPixelToleranceAtAllZooms(0),source);
      if (source.hasTag("natural","water") || source.hasTag("landuse","reservoir"))
        named(features.polygon("water").setZoomRange(5,14),source);
      else if (source.hasTag("landuse") || source.hasTag("leisure","park","garden","nature_reserve") || source.hasTag("natural","wood","scrub","grassland")) {
        Object kind=source.getTag("landuse");
        if (kind==null) kind=source.getTag("leisure");
        if (kind==null) kind=source.getTag("natural");
        named(features.polygon("landuse").setAttr("class",kind).setZoomRange(8,14),source);
      }
    }
    if (source.isPoint() && source.hasTag("place") && source.getTag("name")!=null) {
      String place=String.valueOf(source.getTag("place"));
      int min=place.equals("city")?5:place.equals("town")?8:11;
      named(features.point("places").setAttr("class",place).setZoomRange(min,14),source);
    }
    if (source.hasTag("amenity") || source.hasTag("shop") || source.hasTag("office") || source.hasTag("healthcare") || source.hasTag("tourism")) {
      Object kind=source.getTag("amenity");
      if (kind==null) kind=source.getTag("shop");
      if (kind==null) kind=source.getTag("office");
      if (kind==null) kind=source.getTag("healthcare");
      if (kind==null) kind=source.getTag("tourism");
      if (source.isPoint()) named(features.point("pois").setAttr("class",kind).setZoomRange(14,14),source);
      else if (source.canBePolygon()) named(features.pointOnSurface("pois").setAttr("class",kind).setZoomRange(14,14),source);
    }
  }
  public static void main(String[] argv) throws Exception {
    Arguments args=Arguments.fromArgsOrConfigFile(argv);
    Planetiler.create(args).setProfile(new IndonesiaBasemap())
      .addOsmSource("osm",Path.of("indonesia.osm.pbf"))
      .setOutput(args.getString("output","output archive","indonesia.pmtiles")).run();
  }
}
'''


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def inspect_archive(path,maxzoom=MAXZOOM):
    from pmtiles.reader import Reader
    from pmtiles.tile import TileType,Compression
    with Path(path).open('rb') as f:
        def read(offset,length):f.seek(offset);return f.read(length)
        reader=Reader(read);header=reader.header();metadata=reader.metadata()
    expected={'roads','buildings','water','waterways','landuse','places','coastline','boundaries','pois'}
    layers={row['id'] for row in metadata.get('vector_layers',[])}
    if header['tile_type']!=TileType.MVT or header['max_zoom']!=maxzoom or header['addressed_tiles_count']<=0:
        raise RuntimeError('BASEMAP_ARCHIVE_INVALID_OR_EMPTY')
    if not layers or not layers<=expected:raise RuntimeError('BASEMAP_LAYER_SCHEMA_INVALID')
    if header['tile_compression'] not in {Compression.GZIP,Compression.NONE}:raise RuntimeError('BASEMAP_COMPRESSION_UNSUPPORTED')
    return {'minzoom':header['min_zoom'],'maxzoom':header['max_zoom'],'tiles':header['addressed_tiles_count'],
            'layers':sorted(layers),'bounds':[header[k]/1e7 for k in ['min_lon_e7','min_lat_e7','max_lon_e7','max_lat_e7']],
            'metadata':metadata}


def build_archive(pbf,output,jar,work,bounds,maxzoom=MAXZOOM,heap_gb=JAVA_HEAP_GB):
    work=Path(work);work.mkdir(parents=True,exist_ok=True);source=work/'IndonesiaBasemap.java'
    source.write_text(PROFILE_SOURCE)
    command=['java',f'-Xmx{heap_gb}g','-cp',str(jar),str(source),f'osm_path={pbf}',f'output={output}',
        f'bounds={",".join(map(str,bounds))}',f'maxzoom={maxzoom}','minzoom=0','download=false',
        f'threads={min(4,os.cpu_count() or 1)}','nodemap_type=sparsearray','nodemap_storage=mmap','compress_temp=true',
        f'tmpdir={work/"tmp"}']
    (work/'build_command.json').write_text(json.dumps(command,indent=2))
    with (work/'build.log').open('w') as log:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        for line in process.stdout:print(line.rstrip(),flush=True);log.write(line);log.flush()
        if process.wait():raise RuntimeError('NATIONAL_BASEMAP_BUILD_FAILED: inspect build.log; no READY published')
    return inspect_archive(output,maxzoom)


def ensure_basemap(bucket,work):
    import requests,osmium
    work=Path(work);work.mkdir(parents=True,exist_ok=True)
    identity={'source':PBF_REF,'profile':PROFILE_VERSION,'profile_sha256':hashlib.sha256(PROFILE_SOURCE.encode()).hexdigest(),
              'planetiler_sha256':PLANETILER_SHA,'maxzoom':MAXZOOM}
    pointer=bucket.blob('basemaps/indonesia/'+PROFILE_VERSION+'/'+PBF_REF['sha256']+'/manifest.json')
    if pointer.exists():
        saved=json.loads(pointer.download_as_bytes());blob=bucket.blob(saved['object'],generation=saved['generation']);blob.reload()
        if saved.get('status')!='READY' or saved.get('identity')!=identity or saved.get('source')!=PBF_REF or blob.size!=saved['bytes'] or (blob.metadata or {}).get('sha256')!=saved['sha256'] or blob.crc32c!=saved.get('crc32c'):
            raise RuntimeError('EXISTING_BASEMAP_MANIFEST_INVALID')
        print('BASEMAP READY: gs://'+bucket.name+'/'+pointer.name+' (verified cache)',flush=True);return saved
    pbf=work/'indonesia.osm.pbf'
    if not pbf.exists():
        if shutil.disk_usage(work).free<8*1024**3:raise RuntimeError('NATIONAL_BASEMAP_INSUFFICIENT_DISK')
        blob=bucket.blob(PBF_REF['object'],generation=PBF_REF['generation'])
        print('BASEMAP 1/4: download pinned PBF from GCS — '+str(PBF_REF['bytes'])+' bytes',flush=True)
        blob.download_to_filename(str(pbf)+'.partial',checksum='crc32c',timeout=600)
        Path(str(pbf)+'.partial').replace(pbf)
    if pbf.stat().st_size!=PBF_REF['bytes'] or file_sha(pbf)!=PBF_REF['sha256']:raise RuntimeError('NATIONAL_PBF_HASH_MISMATCH')
    print('BASEMAP 1/4: PBF checksum verified',flush=True)
    with osmium.io.Reader(str(pbf)) as reader:
        header=reader.header();b=header.box();stamp=header.get('osmosis_replication_timestamp')
        if not b.valid() or not stamp:raise RuntimeError('NATIONAL_PBF_HEADER_INCOMPLETE')
        bounds=[b.bottom_left.lon,b.bottom_left.lat,b.top_right.lon,b.top_right.lat]
    java=subprocess.run(['java','--version'],capture_output=True,text=True) if shutil.which('java') else None
    import re
    major=re.search(r'(?:openjdk|java)\s+(\d+)',java.stdout if java else '')
    compiler=subprocess.run(['java','--list-modules'],capture_output=True,text=True) if java else None
    if not major or int(major.group(1))<21 or compiler is None or 'jdk.compiler@' not in compiler.stdout:
        subprocess.run(['apt-get','install','-y','-qq','openjdk-21-jdk-headless'],check=True)
    jar=work/'planetiler.jar'
    if not jar.exists():
        temporary_jar=work/'planetiler.downloading.jar'
        with requests.get(PLANETILER_URL,stream=True,timeout=(20,90)) as r:
            r.raise_for_status()
            with temporary_jar.open('wb') as f:
                for chunk in r.iter_content(8*1024*1024):f.write(chunk)
        if file_sha(temporary_jar)!=PLANETILER_SHA:raise RuntimeError('PLANETILER_BINARY_HASH_MISMATCH')
        temporary_jar.replace(jar)
    if file_sha(jar)!=PLANETILER_SHA:raise RuntimeError('PLANETILER_BINARY_HASH_MISMATCH')
    output=work/'indonesia.pmtiles';receipt=work/'archive_receipt.json'
    if receipt.exists():
        old=json.loads(receipt.read_text())
        if old['identity']!=identity or not output.exists() or file_sha(output)!=old['sha256']:raise RuntimeError('BASEMAP_LOCAL_CACHE_CHANGED')
        stats=inspect_archive(output)
    else:
        if output.exists():raise RuntimeError('INCOMPLETE_BASEMAP_OUTPUT: inspect before rebuilding')
        temporary=output.with_name('indonesia.building.pmtiles')
        if temporary.exists():temporary.unlink()
        print('BASEMAP 2/4: build national vector archive; native CPU passes/sort follow',flush=True)
        stats=build_archive(pbf,temporary,jar,work/'build',bounds)
        temporary.replace(output)
        receipt.write_text(json.dumps({'identity':identity,'sha256':file_sha(output)},indent=2))
    if not {'roads','buildings','water','coastline','places'}<=set(stats['layers']):raise RuntimeError('NATIONAL_BASEMAP_REQUIRED_LAYERS_MISSING')
    print('BASEMAP 3/4: archive validated; tiles='+str(stats['tiles'])+'; layers='+','.join(stats['layers']),flush=True)
    digest=file_sha(output);key='basemaps/indonesia/'+PROFILE_VERSION+'/'+digest+'/indonesia.pmtiles'
    blob=bucket.blob(key);blob.metadata={'sha256':digest,'profile':PROFILE_VERSION}
    print('BASEMAP 4/4: persist verified archive in GCS — '+str(output.stat().st_size)+' bytes',flush=True)
    if not blob.exists():blob.upload_from_filename(str(output),if_generation_match=0,checksum='crc32c',timeout=600)
    blob.reload()
    if blob.size!=output.stat().st_size or (blob.metadata or {}).get('sha256')!=digest:raise RuntimeError('BASEMAP_GCS_VERIFICATION_FAILED')
    manifest={'schema':'indonesia_basemap_v1','status':'READY','object':key,'generation':int(blob.generation),
        'bytes':blob.size,'sha256':digest,'crc32c':blob.crc32c,'source':PBF_REF,'source_as_of':stamp,
        'profile':PROFILE_VERSION,'identity':identity,**stats,
        'attribution':'© OpenStreetMap contributors, ODbL','coverage':'Geofabrik Indonesia extract; mapped features only',
        'display_only':True,'satellite_imagery':False,'overzoom':'Native maxzoom14; client overzoom allowed, not extra detail'}
    pointer.upload_from_string(json.dumps(manifest),content_type='application/json',if_generation_match=0,checksum='crc32c')
    print('BASEMAP READY: gs://'+bucket.name+'/'+pointer.name,flush=True);return manifest
