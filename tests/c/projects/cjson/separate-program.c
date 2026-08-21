#include "cJSON.h"

#include <stdio.h>

int main(void) {
  const char *text = "{\"name\":\"coil\",\"values\":[1,2,3,4],\"ok\":true}";
  cJSON *root = cJSON_Parse(text);
  if (root == NULL) return 1;

  cJSON *name = cJSON_GetObjectItemCaseSensitive(root, "name");
  cJSON *values = cJSON_GetObjectItemCaseSensitive(root, "values");
  int sum = 0;
  cJSON *item = NULL;
  cJSON_ArrayForEach(item, values) { sum += item->valueint; }

  int good = cJSON_IsString(name) &&
             strcmp(name->valuestring, "coil") == 0 && sum == 10;
  char *printed = cJSON_PrintUnformatted(root);
  printf("%s\n%d\n", printed, sum);
  free(printed);
  cJSON_Delete(root);
  return good ? 0 : 2;
}
