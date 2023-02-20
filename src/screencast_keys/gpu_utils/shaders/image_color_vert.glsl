uniform mat4 ModelViewProjectionMatrix;

in vec2 pos;
in vec2 texCoord;
out vec2 connection;

void main()
{
  connection = texCoord;
  gl_Position = ModelViewProjectionMatrix * vec4(pos.xy, 0.0, 1.0);
  gl_Position.z = 1.0;
}
