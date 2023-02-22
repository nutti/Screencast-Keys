uniform vec4 scissor;
uniform vec4 color;

out vec4 fragColor;

void main()
{
  vec2 co = gl_FragCoord.xy;
  if (co.x < scissor.x || co.y < scissor.y ||
      co.x > scissor.z || co.y > scissor.w ) {
    discard;
  }

  fragColor = blender_srgb_to_framebuffer_space(color);
}