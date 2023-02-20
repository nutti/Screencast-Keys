// Ref: source/blender/gpu/shaders/gpu_shader_3D_polyline_geom.glsl

layout (lines) in;
layout (triangle_strip, max_vertices = 4) out;

uniform vec4 color;
uniform float lineWidth;
uniform bool lineSmooth;
uniform vec2 viewportSize;

const float SMOOTH_WIDTH = 1.0;

struct geom_frag_connection {
  vec4 final_color;
  float smoothline;
};

out geom_frag_connection connection;

vec4 clip_line_point_homogeneous_space(vec4 p, vec4 q)
{
  if (p.z < -p.w) {
    float denom = q.z - p.z + q.w - p.w;
    if (denom == 0.0) {
      return p;
    }
    float A = (-p.z - p.w) / denom;
    p = p + (q - p) * A;
  }
  return p;
}

void do_vertex(const int i, vec4 pos, vec2 ofs)
{
  connection.final_color = color;

  connection.smoothline = (lineWidth + SMOOTH_WIDTH * float(lineSmooth)) * 0.5;
  gl_Position = pos;
  gl_Position.xy += ofs * pos.w;
  EmitVertex();

  connection.smoothline = -(lineWidth + SMOOTH_WIDTH * float(lineSmooth)) * 0.5;
  gl_Position = pos;
  gl_Position.xy -= ofs * pos.w;
  EmitVertex();
}

void main(void)
{
  vec4 p0 = clip_line_point_homogeneous_space(gl_in[0].gl_Position, gl_in[1].gl_Position);
  vec4 p1 = clip_line_point_homogeneous_space(gl_in[1].gl_Position, gl_in[0].gl_Position);
  vec2 e = normalize(((p1.xy / p1.w) - (p0.xy / p0.w)) * viewportSize.xy);

  vec2 ofs = vec2(-e.y, e.x);
  ofs /= viewportSize.xy;
  ofs *= lineWidth + SMOOTH_WIDTH * float(lineSmooth);

  do_vertex(0, p0, ofs);
  do_vertex(1, p1, ofs);

  EndPrimitive();
}
