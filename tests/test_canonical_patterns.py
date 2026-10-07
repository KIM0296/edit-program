from dataclasses import FrozenInstanceError
from hashlib import sha256
import struct

import numpy as np
import pytest

from tools.canonical_assets.model import AssetRole, Recipe
from tools.canonical_assets.video_pattern import frame, source_digest
from tools.canonical_assets.glyphs_5x7 import glyph
from tools.canonical_assets.audio_pattern import samples, pack_s24le, pcm
from tools.canonical_assets.wav import wav_bytes, wav_data


def test_recipe_frozen_and_exact():
    recipe = Recipe()
    assert (recipe.width, recipe.height, recipe.frames, recipe.sample_count) == (1280, 720, 720, 1440000)
    with pytest.raises(FrozenInstanceError):
        recipe.frames = 1
    with pytest.raises(TypeError):
        Recipe(frames=1)


def test_glyph_literal_a_and_seven():
    assert glyph('A') == ('01110','10001','10001','11111','10001','10001','10001')
    assert glyph('7') == ('11111','00001','00010','00100','01000','01000','01000')
    for char in '0123456789ABGRV':
        assert len(glyph(char)) == 7
        assert all(len(row)==5 and set(row)<={'0','1'} for row in glyph(char))
    with pytest.raises(ValueError): glyph('X')


@pytest.mark.parametrize('role,rgb',[(AssetRole.ALPHA,(32,96,160)),(AssetRole.BETA,(160,96,32)),(AssetRole.GAMMA,(112,48,160)),(AssetRole.REPEAT,(96,96,96)),(AssetRole.VIDEO_ONLY,(32,128,64))])
def test_background_border_shape(role,rgb):
    image=frame(role,0)
    assert image.shape==(720,1280,3) and image.dtype==np.uint8
    assert tuple(image[500,500])==rgb
    assert tuple(image[0,0])==(235,235,235)
    assert tuple(image[719,1279])==(235,235,235)
    assert tuple(image[8,8])==rgb


def test_independently_audited_video_pixels():
    image=frame(AssetRole.ALPHA,0)
    assert tuple(image[40,40])==(32,96,160)  # A row 0, column 0 is off
    assert tuple(image[40,56])==(255,255,255)  # A row 0, column 1 is on
    assert tuple(image[88,40])==(255,255,255)  # A crossbar row 3
    assert tuple(image[180,40])==(32,96,160)  # digit zero row 0 starts off
    assert tuple(image[180,52])==(255,255,255)
    assert tuple(image[40,1120])==(255,64,64)
    one=frame(AssetRole.ALPHA,1)
    assert tuple(one[520,213])==(240,220,32)
    assert tuple(one[671,228])==(240,220,32)
    assert tuple(one[672,213])==(32,96,160)
    assert tuple(one[40,1120])==(32,32,32)
    twenty_three=frame(AssetRole.ALPHA,23)
    assert tuple(twenty_three[300,52])==(255,255,255)  # 2 row0 01110
    assert tuple(twenty_three[312,40])==(255,255,255)  # 2 row1 10001
    assert tuple(twenty_three[300,112])==(255,255,255)  # 3 row0 starts on
    assert tuple(frame(AssetRole.ALPHA,24)[40,1120])==(255,64,64)
    last=frame(AssetRole.ALPHA,719)
    assert [int(last[400,40+i*36,0]) for i in range(10)]==[240,16,240,240,16,16,240,240,240,240]
    assert tuple(last[180,112])==(255,255,255)  # second digit 7 top-left
    assert tuple(last[520,547])==(240,220,32)


@pytest.mark.parametrize('index',[-1,720,True,1.5])
def test_frame_index_rejected(index):
    with pytest.raises((ValueError,TypeError)): frame(AssetRole.ALPHA,index)


def test_unknown_or_nonvideo_role_rejected():
    for role in ('ALPHA',AssetRole.AUDIO_ONLY):
        with pytest.raises((TypeError,ValueError)): frame(role,0)


def test_source_order_digest_and_repeat_identity():
    a,b=frame(AssetRole.REPEAT,0),frame(AssetRole.REPEAT,1)
    assert a.tobytes()==frame(AssetRole.REPEAT,0).tobytes()
    assert source_digest((a,b))==sha256(a.tobytes()+b.tobytes()).hexdigest()
    assert source_digest((a,b))!=source_digest((b,a))


def test_literal_audio_boundary_samples_both_channels():
    actual=samples(AssetRole.ALPHA)
    # Independently audited integer phase and floor arithmetic, no production helper oracle.
    vectors={0:(0,0),1:(19465,38930),2:(39413,78826),3:(59843,119686),239:(1600826,992651),240:(1677721,838860),719:(-761966,1523930),720:(-838861,1677721),959:(-438655,-171268),960:(-419431,-209716),47999:(-19224,-38448),48000:(0,0),1439999:(-19224,-38448)}
    for index,expected in vectors.items(): assert tuple(actual[index])==expected
    assert actual.shape==(1440000,2)
    assert int(actual.min())>=-8388608 and int(actual.max())<=8388607


def test_pcm_literal_packing_and_interleave():
    data=np.array([[0,1],[-1,8388607],[-8388608,256]],dtype=np.int64)
    assert pack_s24le(data)==bytes.fromhex('000000010000ffffffff7f000080000100')
    with pytest.raises(ValueError): pack_s24le(np.array([[8388608,0]],dtype=np.int64))
    with pytest.raises(TypeError): pack_s24le(np.array([[0.0,1.0]]))
    generated=pcm(AssetRole.ALPHA)
    assert len(generated)==8640000
    assert generated[6:12]==(19465).to_bytes(3,'little',signed=True)+(38930).to_bytes(3,'little',signed=True)
    assert generated==pcm(AssetRole.ALPHA)
    assert pcm(AssetRole.REPEAT)==pcm(AssetRole.REPEAT)
    assert sha256(generated).digest()!=sha256(pcm(AssetRole.BETA)).digest()


def test_wav_literal_header_and_no_extra_chunks():
    data=bytes.fromhex('000000010000ffffffff7f000080000100')
    blob=wav_bytes(data)
    assert blob[:4]==b'RIFF' and blob[8:16]==b'WAVEfmt '
    assert struct.unpack('<IHHIIHH',blob[16:36])==(16,1,2,48000,288000,6,24)
    assert blob[36:40]==b'data' and len(blob)==44+len(data)
    assert int.from_bytes(blob[4:8],'little')==len(blob)-8
    assert blob[44:]==data==wav_data(blob)
    assert blob==wav_bytes(data)
    with pytest.raises(ValueError): wav_data(blob+b'LIST')
    with pytest.raises(ValueError): wav_bytes(b'bad')
