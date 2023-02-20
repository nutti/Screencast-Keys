// Ref: source/blender/gpu/shaders/gpu_shader_3D_polyline_frag.glsl

uniform vec4 color;
uniform float lineWidth;
uniform bool lineSmooth;
uniform vec4 scissor;

const int SMOOTH_WIDTH = 1;

struct geom_frag_connection {
  vec4 final_color;
  float smoothline;
};

in geom_frag_connection connection;
out vec4 fragColor;

void main()
{
  vec2 co = gl_FragCoord.xy;
  if (co.x < scissor.x || co.y < scissor.y ||
      co.x > scissor.z || co.y > scissor.w ) {
    discard;
  }

  fragColor = color;
  if (lineSmooth) {
    fragColor.a *= clamp((lineWidth + SMOOTH_WIDTH) * 0.5 - abs(connection.smoothline), 0.0, 1.0);
  }
  fragColor = blender_srgb_to_framebuffer_space(fragColor);
}
