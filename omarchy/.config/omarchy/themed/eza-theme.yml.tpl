colourful: true
filekinds:
  normal: {foreground: "{{ foreground }}"}
  directory: {foreground: "{{ blue }}"}
  symlink: {foreground: "{{ cyan }}"}
  executable: {foreground: "{{ green }}"}
perms:
  user_read: {foreground: "{{ green }}"}
  user_write: {foreground: "{{ yellow }}"}
  user_execute_file: {foreground: "{{ red }}"}
git:
  new: {foreground: "{{ green }}"}
  modified: {foreground: "{{ yellow }}"}
  deleted: {foreground: "{{ red }}"}
  conflicted: {foreground: "{{ red }}"}
date: {foreground: "{{ yellow }}"}
header: {foreground: "{{ accent }}"}
broken_symlink: {foreground: "{{ red }}"}
