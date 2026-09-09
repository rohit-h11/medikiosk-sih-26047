import { useVoiceContext } from '@/context/VoiceContext';
import { SCREEN_D_TRANSLATIONS, ScreenDTranslationKey } from '@/i18n/translations';

export function useTranslation() {
  const context = useVoiceContext();
  const language = context?.language || 'hi';
  const setLanguage = context?.setLanguage || (() => {});
  const supportedLanguages = context?.supportedLanguages || [];

  const t = (key: ScreenDTranslationKey): string => {
    const langDict = SCREEN_D_TRANSLATIONS[language] || SCREEN_D_TRANSLATIONS['en'];
    return langDict[key] || SCREEN_D_TRANSLATIONS['en'][key] || key;
  };

  return {
    t,
    language,
    setLanguage,
    supportedLanguages,
  };
}
