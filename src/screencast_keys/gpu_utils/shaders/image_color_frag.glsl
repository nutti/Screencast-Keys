uniform sampler2D image;
uniform vec4 color;

in vec2 connection;
out vec4 fragColor;

void main()
{
  fragColor = texture(image, connection) * color;
}