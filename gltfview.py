import sys
import json
import os.path
from ctypes import c_void_p

import OpenGL.GL as gl
import OpenGL.GLU as glu

import cyglfw3 as glfw

import PIL.Image as Image


ATTRIBUTE_TYPE_SIZES = {
    'SCALAR': 1,
    'VEC2': 2,
    'VEC3': 3,
    'VEC4': 4,
    'MAT2': 4,
    'MAT3': 9,
    'MAT4': 16
}
try: # python 3.3 or later
    from types import MappingProxyType
    ATTRIBUTE_TYPE_SIZES = MappingProxyType(ATTRIBUTE_TYPE_SIZES)
except ImportError as err:
    pass


def setup_glfw(width=640, height=480):
    if not glfw.Init():
        print('* failed to initialize glfw')
        exit(1)
    window = glfw.CreateWindow(width, height, "gltfview")
    if not window:
        glfw.Terminate()
        print('* failed to create glfw window')
        exit(1)
    # set up glfw callbacks:
    def on_resize(window, width, height):
        gl.glViewport(0, 0, width, height)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        glu.gluPerspective(50, float(width) / height, 0.1, 1000)
        gl.glMatrixMode(gl.GL_MODELVIEW)
    glfw.SetWindowSizeCallback(window, on_resize)
    def on_keydown(window, key, scancode, action, mods):
        # press ESC to quit:
        if (key == glfw.KEY_ESCAPE and action == glfw.PRESS):
            glfw.SetWindowShouldClose(window, gl.GL_TRUE)
    glfw.SetKeyCallback(window, on_keydown)
    glfw.MakeContextCurrent(window)
    print('GL_VERSION: %s' % gl.glGetString(gl.GL_VERSION))
    on_resize(window, width, height)
    return window


def setup_shaders(gltf, gltf_dir):
    for shader_name, shader in gltf['shaders'].items():
        # TODO: support data URIs
        shader_str = None
        try:
            filename = os.path.join(gltf_dir, shader['uri'])
            shader_str = open(filename).read()
            print('* loaded shader "%s" (from %s):\n%s' % (shader_name, filename, shader_str))
        except Exception as err:
            print('* failed to load shader "%s":\n%s' % (shader_name, err))
            exit(1)
        shader_id = gl.glCreateShader(shader['type'])
        gl.glShaderSource(shader_id, shader_str)
        gl.glCompileShader(shader_id)
        if not gl.glGetShaderiv(shader_id, gl.GL_COMPILE_STATUS):
            print('* failed to compile shader "%s"' % shader_name)
            exit(1)
        print('* compiled shader "%s"' % shader_name)
        shader['id'] = shader_id


def setup_programs(gltf):
    shaders = gltf['shaders']
    for program_name, program in gltf['programs'].items():
        program_id = gl.glCreateProgram()
        gl.glAttachShader(program_id, shaders[program['vertexShader']]['id'])
        gl.glAttachShader(program_id, shaders[program['fragmentShader']]['id'])
        gl.glLinkProgram(program_id)
        gl.glDetachShader(program_id, shaders[program['vertexShader']]['id'])
        gl.glDetachShader(program_id, shaders[program['fragmentShader']]['id'])
        if not gl.glGetProgramiv(program_id, gl.GL_LINK_STATUS):
            print('* failed to link program "%s"' % program_name)
            exit(1)
        program['id'] = program_id
        program['attribute_indices'] = {attribute_name: gl.glGetAttribLocation(program_id, attribute_name)
                                        for attribute_name in program['attributes']}
        print('* linked program "%s"' % program_name)
        print('  attribute indices: %s' % program['attribute_indices'])


def setup_textures(gltf, gltf_dir):
    # TODO: support data URIs
    pil_images = {}
    for image_name, image in gltf['images'].items():
        try:
            filename = os.path.join(gltf_dir, image['uri'])
            pil_image = Image.open(filename)
            pil_images[image_name] = pil_image
            print('* loaded image "%s" (from %s)' % (image_name, filename))
        except Exception as err:
            print('* failed to load image "%s":\n%s' % (image_name, err))
            exit(1)
    for texture_name, texture in gltf['textures'].items():
        texture_id = gl.glGenTextures(1)
        gl.glBindTexture(texture['target'], texture_id)
        # following glview.cc example for now...
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        pixel_format = gl.GL_RGB if image.get('component') == 3 else gl.GL_RGBA
        gl.glTexImage2D(texture['target'], 0, texture['internalFormat'],
                        pil_image.width, pil_image.height, 0,
                        pixel_format, texture['type'],
                        list(pil_image.getdata())) # TODO: better way to pass data?
        # gl.glTexParameterf(texture['target'], gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        # gl.glTexParameterf(texture['target'], gl.GL_TEXTURE_MAX_FILTER, gl.GL_LINEAR)
        if gl.glGetError() != gl.GL_NO_ERROR:
            print('* failed to create texture "%s"' % texture_name)
            exit(1)
        texture['id'] = texture_id
        gl.glBindTexture(texture['target'], 0)
        print('* created texture "%s"' % texture_name)


def setup_buffers(gltf, gltf_dir):
    # TODO: support data URIs
    buffers = gltf['buffers']
    data_buffers = {}
    for buffer_name, buffer in buffers.items():
        try:
            filename = os.path.join(gltf_dir, buffer['uri'])
            if buffer['type'] == 'arraybuffer':
                data_buffers[buffer_name] = open(filename, 'rb').read()
            elif buffer['type'] == 'text':
                pass # TODO
            print('* loaded buffer "%s" (from %s)' % (buffer_name, filename))
        except Exception as err:
            print('* failed to load buffer "%s":\n%s' % (buffer_name, err))
            exit(1)
    for bufferView_name, bufferView in gltf['bufferViews'].items():
        buffer_id = gl.glGenBuffers(1)
        byteOffset, byteLength = bufferView['byteOffset'], bufferView['byteLength']
        gl.glBindBuffer(bufferView['target'], buffer_id)
        gl.glBufferData(bufferView['target'], bufferView['byteLength'],
                        data_buffers[bufferView['buffer']][byteOffset:byteOffset+byteLength], gl.GL_STATIC_DRAW)
        if gl.glGetError() != gl.GL_NO_ERROR:
            print('* failed to create buffer "%s"' % bufferView_name)
            exit(1)
        bufferView['buffer_id'] = buffer_id
        gl.glBindBuffer(bufferView['target'], 0)
        print('* created buffer "%s"' % bufferView_name)


def draw_primitive(primitive, gltf):
    accessors = gltf['accessors']
    bufferViews = gltf['bufferViews']
    textures = gltf['textures']
    material = gltf['materials'][primitive['material']]
    technique = gltf['techniques'][material['technique']]
    program = gltf['programs'][technique['program']]
    # set up GL state for drawing the primitive:
    gl.glUseProgram(program['id'])
    for attribute_name, parameter_name in technique['attributes'].items():
        parameter = technique['parameters'][parameter_name]
        semantic = parameter.get('semantic')
        if semantic:
            accessor = accessors[primitive['attributes'][semantic]]
            bufferView = bufferViews[accessor['bufferView']]
            buffer_id = bufferView['buffer_id']
            gl.glBindBuffer(bufferView['target'], buffer_id)
            attribute_index = program['attribute_indices'][attribute_name]
            gl.glVertexAttribPointer(attribute_index, ATTRIBUTE_TYPE_SIZES[accessor['type']],
                                     accessor['componentType'], False, accessor['byteStride'], accessor['byteOffset'])
            gl.glEnableVertexAttribArray(attribute_index)
    material_values = material.get('values', {})
    for uniform_name, parameter_name in technique['uniforms'].items():
        parameter = technique['parameters'][parameter_name]
        semantic = parameter.get('semantic')
        if semantic:
            pass # TODO
        else:
            location = gl.glGetUniformLocation(program['id'], uniform_name)
            value = material_values.get(parameter_name, parameter.get('value'))
            if value:
                if parameter['type'] == gl.GL_SAMPLER_2D:
                    texture = textures[value]
                    gl.glUniform1i(location, texture['id'])
                    gl.glBindTexture(texture['target'], texture['id'])
                elif parameter['type'] == gl.GL_FLOAT:
                    gl.glUniform1f(location, value)
                elif parameter['type'] == gl.GL_FLOAT_VEC3:
                    gl.glUniform3f(location, *value)
                elif parameter['type'] == gl.GL_FLOAT_VEC4:
                    gl.glUniform4f(location, *value)
                else:
                    print('* unhandled type: %s' % parameter['type'])
    index_accessor = accessors[primitive['indices']]
    index_bufferView = bufferViews[index_accessor['bufferView']]
    gl.glBindBuffer(index_bufferView['target'], index_bufferView['buffer_id'])
    # draw:
    gl.glDrawElements(primitive['mode'], index_accessor['count'], index_accessor['componentType'],
                      c_void_p(index_accessor['byteOffset']))
    if gl.glGetError() != gl.GL_NO_ERROR:
        print('* error drawing elements')
        exit(1)

        
def display_gltf(window, gltf, scene=None):
    if scene is None:
        scene = gltf['scenes'][gltf['scene']]

    # testing >>>>>>
    mesh = list(gltf['meshes'].values())[0]
    primitive = mesh['primitives'][0]
    # main loop:
    while not glfw.WindowShouldClose(window):
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        draw_primitive(primitive, gltf)
        glfw.SwapBuffers(window)
        glfw.PollEvents()
    # <<<<<< testing

    # cleanup:
    print('* quiting...')
    glfw.DestroyWindow(window)
    glfw.Terminate()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('usage: python %s <path to gltf file>' % sys.argv[0])
        exit()

    gltf = None
    try:
        gltf = json.loads(open(sys.argv[1]).read())
        print('* loaded %s' % sys.argv[1])
    except Exception as err:
        print('* failed to load %s:\n%s' % (sys.argv[1], err))
        exit(1)
    gltf_dir = os.path.dirname(sys.argv[1])

    sys.stdout.flush()

    window = setup_glfw()

    setup_shaders(gltf, gltf_dir)
    setup_programs(gltf)
    setup_textures(gltf, gltf_dir)
    setup_buffers(gltf, gltf_dir)

    sys.stdout.flush()

    display_gltf(window, gltf)
