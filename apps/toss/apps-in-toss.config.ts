import { defineConfig } from '@apps-in-toss/web-framework/config';

// 콘솔에 등록한 실제 appName을 환경변수로 제공한다. 임의 운영 ID를 만들지 않는다.
const appName = process.env.TOSS_APP_NAME;
if (!appName) throw new Error('콘솔에 등록한 TOSS_APP_NAME을 설정해 주세요.');
export default defineConfig({
  appName,
  brand: { primaryColor: '#2d6050' },
  permissions: [],
  webBundleDir: 'dist',
});
