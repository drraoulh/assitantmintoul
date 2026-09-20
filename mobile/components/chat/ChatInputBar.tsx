import { useState } from 'react';
import {
  Alert,
  InteractionManager,
  Keyboard,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { setAudioModeAsync } from 'expo-audio';
import * as Haptics from 'expo-haptics';
import * as ImagePicker from 'expo-image-picker';

import { colors, radius, spacing } from '../../constants/theme';
import { useLocale } from '../../i18n';
import { IconCircleButton } from '../ui/IconCircleButton';

interface ChatInputBarProps {
  disabled?: boolean;
  onSend: (message: string) => void;
  onSendImage: (asset: {
    uri: string;
    mimeType?: string;
    fileName?: string | null;
    file?: Blob | null;
    base64?: string | null;
  }) => void;
  onOpenVoiceMode: () => void;
}

const PICKER_OPTIONS: ImagePicker.ImagePickerOptions = {
  mediaTypes: ['images'],
  quality: 0.7,
  allowsEditing: false,
  exif: false,
  // Needed on web when blob URI fetch fails (Safari "Load failed").
  base64: Platform.OS === 'web',
  ...(Platform.OS === 'ios'
    ? {
        presentationStyle:
          ImagePicker.UIImagePickerPresentationStyle.FULL_SCREEN,
      }
    : {}),
};

function runAfterUiSettles(task: () => Promise<void>) {
  // Web: browsers only allow the file picker inside a direct user gesture.
  // Delaying (or awaiting a modal close) blocks the input[type=file] click.
  if (Platform.OS === 'web') {
    void task();
    return;
  }

  InteractionManager.runAfterInteractions(() => {
    // iOS needs the previous modal fully dismissed before UIImagePickerController.
    setTimeout(() => {
      void task();
    }, Platform.OS === 'ios' ? 450 : 150);
  });
}

export function ChatInputBar({
  disabled = false,
  onSend,
  onSendImage,
  onOpenVoiceMode,
}: ChatInputBarProps) {
  const { t } = useLocale();
  const [value, setValue] = useState('');
  const [photoMenuOpen, setPhotoMenuOpen] = useState(false);

  const submit = () => {
    const next = value.trim();
    if (!next || disabled) {
      return;
    }
    onSend(next);
    setValue('');
  };

  const prepareForPicker = async () => {
    // Voice mode may leave the audio session in recording mode, which blocks camera on iOS.
    try {
      await setAudioModeAsync({
        allowsRecording: false,
        playsInSilentMode: true,
      });
    } catch {
      // ignore — camera can still work if audio mode fails
    }
  };

  const pickFromLibrary = async () => {
    try {
      if (Platform.OS !== 'web') {
        await prepareForPicker();
        const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (!permission.granted) {
          Alert.alert(t('photo.permTitle'), t('photo.permBody'));
          return;
        }
      }

      const result = await ImagePicker.launchImageLibraryAsync(PICKER_OPTIONS);
      if (!result.canceled && result.assets[0]?.uri) {
        const asset = result.assets[0];
        onSendImage({
          uri: asset.uri,
          mimeType: asset.mimeType ?? undefined,
          fileName: asset.fileName,
          file: asset.file ?? null,
          base64: asset.base64 ?? null,
        });
      }
    } catch (error) {
      Alert.alert(
        t('photo.permTitle'),
        error instanceof Error ? error.message : t('gallery.error'),
      );
    }
  };

  const takePhoto = async () => {
    try {
      if (Platform.OS !== 'web') {
        await prepareForPicker();
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!permission.granted) {
          Alert.alert(t('camera.permTitle'), t('camera.permBody'));
          return;
        }
      }

      const result = await ImagePicker.launchCameraAsync(PICKER_OPTIONS);
      if (!result.canceled && result.assets[0]?.uri) {
        const asset = result.assets[0];
        onSendImage({
          uri: asset.uri,
          mimeType: asset.mimeType ?? undefined,
          fileName: asset.fileName,
          file: asset.file ?? null,
          base64: asset.base64 ?? null,
        });
      }
    } catch (error) {
      Alert.alert(
        t('camera.permTitle'),
        error instanceof Error ? error.message : t('camera.error'),
      );
    }
  };

  const openPhotoOptions = () => {
    if (disabled) {
      return;
    }
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    Keyboard.dismiss();
    setPhotoMenuOpen(true);
  };

  return (
    <View style={styles.stack}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t('a11y.voiceMode')}
        disabled={disabled}
        onPress={() => {
          void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
          onOpenVoiceMode();
        }}
        style={({ pressed }) => [
          styles.voiceEntry,
          disabled && styles.voiceEntryDisabled,
          pressed && !disabled && styles.voiceEntryPressed,
        ]}
      >
        <View style={styles.voiceIcon}>
          <Ionicons name="mic" size={18} color={colors.forestDeep} />
        </View>
        <View style={styles.voiceCopy}>
          <Text style={styles.voiceTitle}>{t('voice.modeTitle')}</Text>
          <Text style={styles.voiceSubtitle}>{t('voice.modeSub')}</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.canopy} />
      </Pressable>

      <View style={styles.wrap}>
        <IconCircleButton
          name="camera-outline"
          accessibilityLabel={t('a11y.attachPhoto')}
          disabled={disabled}
          onPress={openPhotoOptions}
        />
        <TextInput
          value={value}
          onChangeText={setValue}
          placeholder={t('input.placeholder')}
          placeholderTextColor={colors.muted}
          multiline
          editable={!disabled}
          style={styles.input}
          onSubmitEditing={() => {
            Keyboard.dismiss();
            submit();
          }}
        />
        <IconCircleButton
          name="send"
          variant="solid"
          accessibilityLabel={t('a11y.send')}
          disabled={disabled || value.trim().length === 0}
          onPress={submit}
        />
      </View>

      <Modal
        visible={photoMenuOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setPhotoMenuOpen(false)}
      >
        <Pressable
          style={styles.sheetBackdrop}
          onPress={() => setPhotoMenuOpen(false)}
        >
          <Pressable
            style={styles.sheet}
            onPress={(event) => event.stopPropagation()}
          >
            <Text style={styles.sheetTitle}>{t('photo.title')}</Text>
            <Text style={styles.sheetSubtitle}>{t('photo.subtitle')}</Text>

            <Pressable
              accessibilityRole="button"
              onPress={() => {
                // Close sheet after starting picker so the web file dialog stays
                // tied to this click (user-gesture).
                runAfterUiSettles(takePhoto);
                setPhotoMenuOpen(false);
              }}
              style={({ pressed }) => [
                styles.sheetAction,
                pressed && styles.sheetActionPressed,
              ]}
            >
              <Ionicons name="camera" size={20} color={colors.forest} />
              <Text style={styles.sheetActionLabel}>{t('photo.take')}</Text>
            </Pressable>

            <Pressable
              accessibilityRole="button"
              onPress={() => {
                runAfterUiSettles(pickFromLibrary);
                setPhotoMenuOpen(false);
              }}
              style={({ pressed }) => [
                styles.sheetAction,
                pressed && styles.sheetActionPressed,
              ]}
            >
              <Ionicons name="images" size={20} color={colors.forest} />
              <Text style={styles.sheetActionLabel}>{t('photo.library')}</Text>
            </Pressable>

            <Pressable
              accessibilityRole="button"
              onPress={() => setPhotoMenuOpen(false)}
              style={styles.sheetCancel}
            >
              <Text style={styles.sheetCancelLabel}>{t('photo.cancel')}</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  stack: {
    gap: 10,
  },
  voiceEntry: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: colors.forest,
    borderRadius: radius.lg,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  voiceEntryDisabled: {
    opacity: 0.5,
  },
  voiceEntryPressed: {
    opacity: 0.88,
  },
  voiceIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.gold,
  },
  voiceCopy: {
    flex: 1,
  },
  voiceTitle: {
    color: colors.ivory,
    fontSize: 15,
    fontWeight: '700',
  },
  voiceSubtitle: {
    color: 'rgba(255,251,244,0.7)',
    fontSize: 12,
    marginTop: 1,
  },
  wrap: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    backgroundColor: colors.ivory,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: 8,
  },
  input: {
    flex: 1,
    maxHeight: 110,
    minHeight: 42,
    paddingHorizontal: spacing.sm,
    paddingVertical: 10,
    color: colors.ink,
    fontSize: 16,
  },
  sheetBackdrop: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0, 41, 30, 0.5)',
  },
  sheet: {
    backgroundColor: colors.ivory,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.lg,
    gap: 10,
  },
  sheetTitle: {
    color: colors.ink,
    fontSize: 17,
    fontWeight: '700',
  },
  sheetSubtitle: {
    color: colors.muted,
    fontSize: 13,
    marginBottom: 4,
  },
  sheetAction: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: colors.sand,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 14,
  },
  sheetActionPressed: {
    opacity: 0.85,
  },
  sheetActionLabel: {
    color: colors.ink,
    fontSize: 15,
    fontWeight: '600',
  },
  sheetCancel: {
    alignItems: 'center',
    paddingVertical: 10,
  },
  sheetCancelLabel: {
    color: colors.canopy,
    fontSize: 15,
    fontWeight: '600',
  },
});
