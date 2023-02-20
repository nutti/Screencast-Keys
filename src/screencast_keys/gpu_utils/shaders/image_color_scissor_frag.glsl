uniform sampler2D image;
uniform vec4 color;
uniform vec4 scissor;

in vec2 connection;
out vec4 fragColor;

void main()
{
  vec2 co = gl_FragCoord.xy;
  if (co.x < scissor.x || co.y < scissor.y ||
      co.x > scissor.z || co.y > scissor.w ) {
    discard;
  }

  fragColor = texture(image, connection) * color;
}