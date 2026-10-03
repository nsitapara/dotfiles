// Validate the actual upstream serializer used by the local yabai patch.
// No events are posted, so this test does not require Accessibility access.
#include <assert.h>
#include "event_serialize.c"

int main(void)
{
    assert(iss_augment_dock_swipe_event(NULL) == NULL);
    const int phases[] = {1, 2, 4};
    for (int direction = -1; direction <= 1; direction += 2) {
        for (int i = 0; i < 3; ++i) {
            CGEventRef event = CGEventCreate(NULL);
            assert(event);
            CGEventSetIntegerValueField(event, 55, 30);
            CGEventSetIntegerValueField(event, 110, 23);
            CGEventSetIntegerValueField(event, 123, 1);
            CGEventSetIntegerValueField(event, 132, phases[i]);
            CGEventSetDoubleValueField(event, 124, direction * 0.000016);
            if (phases[i] == 4) CGEventSetDoubleValueField(event, 129, direction * 9999.0);
            CGEventRef augmented = iss_augment_dock_swipe_event(event);
            assert(augmented);
            assert(CGEventGetIntegerValueField(augmented, 132) == phases[i]);
            CFDataRef data = CGEventCreateData(NULL, augmented);
            assert(data);
            ISSCGEventParsedData parsed = {0};
            assert(iss_parse_event_data(CFDataGetBytePtr(data), CFDataGetLength(data), &parsed));
            int payloads = 0;
            for (size_t j = 0; j < parsed.field_count; ++j) {
                ISSCGEventParsedField *field = &parsed.fields[j];
                if (field->field_id != 4205) continue;
                ++payloads;
                size_t expected = sizeof(IOHIDSystemQueueElementHeader) + sizeof(IOHIDFluidTouchGestureData);
                if (phases[i] == 4) expected += sizeof(IOHIDVelocityEventData);
                assert(field->payload_length == expected);
                IOHIDSystemQueueElementHeader *header = (void *)field->payload;
                assert(header->event_count == (phases[i] == 4 ? 2 : 1));
                IOHIDFluidTouchGestureData *fluid = (void *)(field->payload + sizeof(*header));
                assert(fluid->base.options == (uint32_t)phases[i] << 24);
                assert(fluid->swipe_progress == direction);
                assert(fluid->gesture_motion == 1 && fluid->gesture_flavor == 3);
                if (phases[i] == 4) {
                    IOHIDVelocityEventData *velocity = (void *)((uint8_t *)fluid + sizeof(*fluid));
                    assert(velocity->velocity_x == direction * 9999 * 65536);
                }
            }
            assert(payloads == 1);
            iss_parsed_event_data_free(&parsed);
            CFRelease(data);
            CFRelease(augmented);
            CFRelease(event);
        }
    }
    puts("Dock swipe payloads passed for both directions and all three phases.");
    return 0;
}
