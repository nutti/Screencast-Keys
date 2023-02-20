// Ref: source/blender/gpu/shaders/gpu_shader_3D_polyline_vert.glsl

uniform mat4 ModelViewProjectionMatrix;

in vec3 pos;

void main()
{
  gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);
}
