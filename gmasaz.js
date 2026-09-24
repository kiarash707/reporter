const TelegramBot = require('node-telegram-bot-api');
const fs = require('fs');
const path = require('path');
const axios = require('axios');
const moment = require('moment');
const crypto = require('crypto');

const TOKEN = process.env.BOT_TOKEN || '8900817385:AAHyS68xNndiekeGDgzlC3KuaUwnKsk';

const ADMIN_IDS = [8111965995];

const BOT_SETTINGS = {
    maintenance: false,
    force_join: false,
    channel_username: '',
    channel_id: '',
    max_emails_per_user: 99,
    cooldown_seconds: 60
};

const SETTINGS_FILE = 'bot_settings.json';

const loadSettings = () => {
    try {
        if (fs.existsSync(SETTINGS_FILE)) {
            const data = fs.readFileSync(SETTINGS_FILE, 'utf8');
            const settings = JSON.parse(data);
            Object.assign(BOT_SETTINGS, settings);
        }
    } catch (error) {
        console.log('خطا در بارگذاری تنظیمات:', error);
    }
};

const saveSettings = () => {
    try {
        fs.writeFileSync(SETTINGS_FILE, JSON.stringify(BOT_SETTINGS, null, 2));
    } catch (error) {
        console.log('خطا در ذخیره تنظیمات:', error);
    }
};

const bot = new TelegramBot(TOKEN, { polling: true });

console.log(`🤖 ربات آنلاین شد...`);

const ensureDirectories = () => {
    const directories = ['Accounts', 'Accounts/mails', 'Backups', 'BannedUsers'];
    directories.forEach(dir => {
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
            console.log(`✅ پوشه ${dir} ایجاد شد`);
        }
    });
};

const userStats = new Map();

const bannedUsers = new Set();

const loadBannedUsers = () => {
    try {
        if (fs.existsSync('BannedUsers/list.json')) {
            const data = fs.readFileSync('BannedUsers/list.json', 'utf8');
            const banned = JSON.parse(data);
            banned.forEach(userId => bannedUsers.add(userId));
        }
    } catch (error) {
        console.log('خطا در بارگذاری لیست مسدود شده‌ها:', error);
    }
};

const saveBannedUsers = () => {
    try {
        const bannedArray = Array.from(bannedUsers);
        fs.writeFileSync('BannedUsers/list.json', JSON.stringify(bannedArray, null, 2));
    } catch (error) {
        console.log('خطا در ذخیره لیست مسدود شده‌ها:', error);
    }
};

const isUserBanned = (userId) => {
    return bannedUsers.has(userId.toString());
};

const banUser = (userId) => {
    bannedUsers.add(userId.toString());
    saveBannedUsers();
    return true;
};

const unbanUser = (userId) => {
    bannedUsers.delete(userId.toString());
    saveBannedUsers();
    return true;
};

const PERSIAN_TEXTS = {
    'welcome_back': `🎉 خوش برگشتی {name}!

✨ ربات ایمیل موقت شما آماده است
📧 از منوی زیر استفاده کن:`,

    'welcome_new': `🎊 سلام {name} عزیز!

✨ به ربات ایمیل موقت خوش آمدی
📧 ایمیل‌های موقت و امن، فقط با یک لمس

از منوی زیر شروع کن:`,

    'mail_menu_title': `🔮 منوی ایمیل موقت

✨ انتخاب کنید:`,

    'generating_email': `⏳ در حال ایجاد ایمیل...

✨ لطفاً صبر کنید
⏱️ ممکن است تا یک دقیقه طول بکشد`,

    'no_emails': `📭 هنوز هیچ ایمیلی نداری

✨ از منوی /mail ایمیل جدید بساز`,

    'email_list_title': `📋 لیست ایمیل‌های شما

✨ روی هر کدام کلیک کن تا جزئیات را ببینی`,

    'delete_confirm': `⚠️ آیا مطمئنی که می‌خوای این ایمیل را حذف کنی؟

🗑️ این عملیات قابل بازگشت نیست`,

    'email_deleted': "✅ ایمیل با موفقیت حذف شد",
    'operation_cancelled': "❌ عملیات لغو شد",
    'error_occurred': "❌ خطایی رخ داد! دوباره امتحان کن",

    'stats_title': `📊 آمار کاربری

✨ اطلاعات کامل شما:`,

    'stats_emails': "📧 تعداد ایمیل‌ها: {count}",
    'stats_created': "🆕 ایمیل‌های ایجاد شده: {count}",
    'stats_last_activity': "🕐 آخرین فعالیت: {time}",

    'help_text': `🤖 راهنمای ربات ایمیل موقت

✨ قابلیت‌ها:
• 🔮 ایجاد ایمیل موقت
• 📬 مشاهده صندوق ورودی
• 🗑️ مدیریت ایمیل‌ها
• 📊 آمار کاربری

🔧 دستورات:
/start - شروع ربات
/mail - منوی اصلی
/stats - آمار کاربری
/help - راهنما

💡 نکات:
• هر کاربر تا 99 ایمیل می‌تواند بسازد
• ایمیل‌ها موقت و امن هستند
• پیوست‌ها پشتیبانی می‌شوند
• رابط کاربری مدرن و زیبا`,

    'email_created_success': `🎉 ایمیل شما با موفقیت ایجاد شد!

✨ ایمیل شما آماده استفاده است
📧 می‌توانید از منوی /mail صندوق ورودی را ببینید

🔮 ایمیل شما:`,

    'inbox_empty': `📭 صندوق ورودی خالی است!

✨ بعد از چند دقیقه دوباره امتحان کنید`,

    'inbox_loading': `⏳ در حال بارگذاری صندوق ورودی...

✨ لطفاً صبر کنید`,

    'attachment_support': `📎 پیوست‌ها پشتیبانی می‌شوند
🔐 می‌توانی از این ایمیل برای تایید OTP یا لینک استفاده کنی`,

    'delete_all_confirm': `⚠️ آیا مطمئنی که می‌خوای همه ایمیل‌ها را حذف کنی؟

🗑️ این عملیات قابل بازگشت نیست`,

    'all_emails_deleted': "✅ همه ایمیل‌ها با موفقیت حذف شدند",

    'email_info_title': `📧 اطلاعات ایمیل

✨ جزئیات کامل:`,

    'email_info_username': "👤 نام کاربری: {username}",
    'email_info_password': "🔑 رمز عبور: {password}",
    'email_info_token': "🔐 توکن: {token}...",
    'email_info_created': "📅 تاریخ ایجاد: {date}",
    'email_info_domain': "🌐 دامنه: {domain}",

    'mailbox_title': `📬 صندوق ورودی

✨ ایمیل‌های دریافتی:`,

    'message_from': "👤 از: {name}\n📧 {address}\n\n",
    'message_subject': "📋 موضوع: {subject}\n\n",
    'message_content': "📄 محتوا:\n{content}",
    'no_subject': "📋 موضوع: بدون موضوع\n\n",
    'empty_message': "📄 محتوا: پیام خالی یا قابل دریافت نیست",

    'admin_panel_title': `🔐 پنل ادمین

✨ مدیریت ربات:`,

    'admin_stats_title': `📊 آمار کلی ربات

✨ اطلاعات کامل:`,

    'admin_stats_users': "👥 تعداد کاربران: {count}",
    'admin_stats_emails': "📧 تعداد ایمیل‌ها: {count}",
    'admin_stats_today': "📅 ایمیل‌های امروز: {count}",
    'admin_stats_online': "🟢 ربات آنلاین",
    'admin_stats_banned': "🚫 کاربران مسدود: {count}",
    'admin_stats_maintenance': "🔧 حالت تعمیر: {status}",
    'admin_stats_force_join': "📢 عضویت اجباری: {status}",

    'admin_broadcast_title': `📢 ارسال پیام همگانی

✨ پیام خود را ارسال کنید:`,

    'admin_broadcast_sent': "✅ پیام با موفقیت ارسال شد\n📊 تعداد دریافت‌کنندگان: {count}",

    'admin_user_management': `👥 مدیریت کاربران

✨ انتخاب کنید:`,

    'admin_user_list': "📋 لیست کاربران",
    'admin_user_search': "🔍 جستجوی کاربر",
    'admin_user_ban': "🚫 مسدود کردن کاربر",
    'admin_user_unban': "✅ آزاد کردن کاربر",
    'admin_user_info': "👤 اطلاعات کاربر",

    'admin_settings': `⚙️ تنظیمات ربات

✨ انتخاب کنید:`,

    'admin_settings_maintenance': "🔧 حالت تعمیر: {status}",
    'admin_settings_force_join': "📢 عضویت اجباری: {status}",
    'admin_settings_limits': "📊 تنظیم محدودیت‌ها",
    'admin_settings_backup': "💾 پشتیبان‌گیری",
    'admin_settings_set_channel': "📢 تنظیم کانال اجباری",

    'admin_maintenance_on': "🔧 حالت تعمیر فعال شد",
    'admin_maintenance_off': "🔧 حالت تعمیر غیرفعال شد",
    'admin_force_join_on': "📢 عضویت اجباری فعال شد",
    'admin_force_join_off': "📢 عضویت اجباری غیرفعال شد",

    'enter_channel_username': "📢 لطفاً یوزرنیم کانال را وارد کنید (با @ شروع شود):",
    'enter_channel_id': "📢 لطفاً آیدی عددی کانال را وارد کنید:",
    'channel_set_success': "✅ کانال با موفقیت تنظیم شد\n📢 یوزرنیم: {username}\n🆔 آیدی: {id}",
    'invalid_channel_username': "❌ یوزرنیم کانال نامعتبر است",
    'invalid_channel_id': "❌ آیدی کانال نامعتبر است",

    'enter_user_id': "👤 لطفاً آیدی کاربر را وارد کنید:",
    'user_not_found': "❌ کاربر یافت نشد",
    'user_banned': "✅ کاربر با موفقیت مسدود شد",
    'user_unbanned': "✅ کاربر با موفقیت آزاد شد",
    'user_already_banned': "⚠️ کاربر قبلاً مسدود شده",
    'user_not_banned': "⚠️ کاربر مسدود نیست",
    'user_info': `👤 اطلاعات کاربر
🆔 آیدی: {id}
👤 نام: {name}
📅 تاریخ عضویت: {join_date}
📊 ایمیل‌ها: {email_count}
🚫 وضعیت: {status}`,

    'enter_max_emails': "📊 لطفاً حداکثر تعداد ایمیل‌های هر کاربر را وارد کنید:",
    'enter_cooldown': "⏱️ لطفاً زمان انتظار بین ساخت ایمیل‌ها را وارد کنید (ثانیه):",
    'limits_updated': "✅ محدودیت‌ها با موفقیت به‌روزرسانی شد",

    'backup_created': "💾 پشتیبان با موفقیت ایجاد شد",
    'backup_restored': "💾 پشتیبان با موفقیت بازیابی شد",

    'force_join_message': `📢 برای استفاده از ربات، باید در کانال زیر عضو شوید:

🔗 {channel}

✅ پس از عضویت، دوباره /start را بزنید.`,
    
    'not_member': `❌ شما در کانال عضو نیستید.

📢 لطفاً در کانال زیر عضو شوید و دوباره امتحان کنید:
🔗 {channel}`
};

const isAdmin = (userId) => ADMIN_IDS.includes(userId);

const checkChannelMembership = async (userId) => {
    if (!BOT_SETTINGS.force_join || !BOT_SETTINGS.channel_username) {
        return true;
    }

    try {
        const chatMember = await bot.getChatMember(BOT_SETTINGS.channel_id || BOT_SETTINGS.channel_username, userId);
        return ['creator', 'administrator', 'member'].includes(chatMember.status);
    } catch (error) {
        console.log('خطا در بررسی عضویت:', error);
        return false;
    }
};

const updateUserStats = (userId, action = 'activity', userName = null) => {
    const key = userId.toString();

    if (!userStats.has(key)) {
        userStats.set(key, {
            emails_created: 0,
            last_activity: null,
            total_emails: 0,
            join_date: new Date(),
            name: userName || 'ناشناس'
        });
    }

    const stats = userStats.get(key);
    stats.last_activity = new Date();

    if (userName) {
        stats.name = userName;
    }

    if (action === 'email_created') {
        stats.emails_created++;
        stats.total_emails++;
    }

    userStats.set(key, stats);
};

const getUserStats = (userId) => {
    const key = userId.toString();

    if (!userStats.has(key)) {
        return {
            emails_created: 0,
            total_emails: 0,
            last_activity: "نامشخص",
            join_date: "نامشخص",
            name: 'ناشناس'
        };
    }

    const stats = userStats.get(key);
    const userMailsDir = `Accounts/${userId}/mails/`;
    
    if (fs.existsSync(userMailsDir)) {
        stats.total_emails = fs.readdirSync(userMailsDir).length;
    } else {
        stats.total_emails = 0;
    }

    const lastActivity = stats.last_activity ? 
        moment(stats.last_activity).format('YYYY-MM-DD HH:mm') : 
        "نامشخص";

    const joinDate = stats.join_date ? 
        moment(stats.join_date).format('YYYY-MM-DD HH:mm') : 
        "نامشخص";

    return {
        emails_created: stats.emails_created,
        total_emails: stats.total_emails,
        last_activity: lastActivity,
        join_date: joinDate,
        name: stats.name || 'ناشناس'
    };
};

const smartRandomString = (length) => {
    const vowels = 'aeiou';
    const consonants = 'bcdfghjklmnpqrstvwxyz';
    let randomString = '';

    while (randomString.length < length) {
        if (randomString.length % 2 === 0) {
            randomString += consonants[Math.floor(Math.random() * consonants.length)];
        } else {
            randomString += vowels[Math.floor(Math.random() * vowels.length)];
        }
    }

    return randomString.substring(0, length);
};

const decodeMIME = (mimeMessage) => {
    try {
        const patterns = [
            /Content-Type: text\/plain; charset=utf-8\r\nContent-Transfer-Encoding: base64\r\n\r\n(.*?)--/s,
            /Content-Type: text\/plain[^\r\n]*\r\n\r\n(.*?)(?=\r\n--|$)/s,
            /Content-Type: text\/[^\r\n]*\r\n\r\n(.*?)(?=\r\n--|$)/s,
            /\r\n\r\n(.*?)(?=\r\n--|$)/s
        ];

        for (const pattern of patterns) {
            const match = mimeMessage.match(pattern);
            if (match && match[1]) {
                let content = match[1].trim();
                
                if (content.includes('base64')) {
                    try {
                        const base64Match = content.match(/base64\r\n\r\n(.*?)(?=\r\n--|$)/s);
                        if (base64Match) {
                            content = Buffer.from(base64Match[1], 'base64').toString('utf-8');
                        }
                    } catch (e) {
                        console.log('خطا در دکود base64:', e);
                    }
                }

                return extractImportantContent(content);
            }
        }

        return "محتوا قابل نمایش نیست یا ایمیل خالی است.";
    } catch (error) {
        console.log('خطا در decodeMIME:', error);
        return "خطا در خواندن محتوا";
    }
};

const extractImportantContent = (text) => {
    try {
        text = text.replace(/<[^>]+>/g, '');
        
        text = text.replace(/\s+/g, ' ').trim();

        const verificationPatterns = [
            /verification code[:\s]*([A-Z0-9]{6,8})/i,
            /code[:\s]*([A-Z0-9]{6,8})/i,
            /enter the code[:\s]*([A-Z0-9]{6,8})/i,
            /your code[:\s]*([A-Z0-9]{6,8})/i
        ];

        for (const pattern of verificationPatterns) {
            const match = text.match(pattern);
            if (match) {
                return `🔐 کد تایید: ${match[1]}`;
            }
        }

        const standaloneCode = text.match(/\b([A-Z0-9]{6,8})\b/);
        if (standaloneCode) {
            const code = standaloneCode[1];
            if (code.match(/[A-Z]/) && code.match(/[0-9]/)) {
                return `🔐 کد تایید: ${code}`;
            }
        }

        const importantKeywords = ['verification', 'confirm', 'activate', 'code', 'password', 'تایید', 'فعال‌سازی', 'کد', 'رمز'];
        const lines = text.split('\n');
        const importantLines = [];

        for (const line of lines) {
            const trimmedLine = line.trim();
            if (importantKeywords.some(keyword => 
                trimmedLine.toLowerCase().includes(keyword.toLowerCase())) && 
                trimmedLine.length > 3) {
                importantLines.push(trimmedLine);
            }
        }

        if (importantLines.length > 0) {
            return importantLines.slice(0, 3).join('\n');
        }

        const meaningfulLines = lines
            .map(line => line.trim())
            .filter(line => line.length > 10 && !line.startsWith('http'))
            .slice(0, 3);

        if (meaningfulLines.length > 0) {
            return meaningfulLines.join('\n');
        }

        return "محتوا قابل نمایش نیست";
    } catch (error) {
        console.log('خطا در extractImportantContent:', error);
        return "خطا در استخراج محتوا";
    }
};

const generateEmail = async (userId) => {
    try {
        const userDir = `Accounts/${userId}/mails/`;
        if (fs.existsSync(userDir)) {
            const emailCount = fs.readdirSync(userDir).length;
            if (emailCount >= BOT_SETTINGS.max_emails_per_user) {
                return {
                    success: false,
                    message: `❌ شما به حداکثر تعداد ایمیل‌ها (${BOT_SETTINGS.max_emails_per_user}) رسیده‌اید`
                };
            }
        }

        const username = smartRandomString(8);
        const password = smartRandomString(8);

        const domainsResponse = await axios.get('https://api.mail.tm/domains', { timeout: 10000 });
        const domains = domainsResponse.data['hydra:member'];
        
        let domain = '';
        for (const d of domains) {
            if (d.isActive) {
                domain = d.domain;
                break;
            }
        }

        if (!domain) {
            throw new Error('هیچ دامنه‌ای یافت نشد');
        }

        const accountData = {
            address: `${username}@${domain}`,
            password: password
        };

        const accountResponse = await axios.post('https://api.mail.tm/accounts', 
            accountData, 
            { headers: { 'Content-Type': 'application/json' } }
        );

        const createdAt = accountResponse.data.createdAt.replace('T', ' ').split('.')[0];

        const tokenResponse = await axios.post('https://api.mail.tm/token', 
            accountData,
            { headers: { 'Content-Type': 'application/json' } }
        );

        const token = tokenResponse.data.token;

        const emailInfo = [
            `account_addrs:${username}`,
            `account_psswd:${password}`,
            `account_token:${token}`,
            `account_creat:${createdAt}`,
            `account_mail_name:${domain}`
        ].join('\n');

        const emailFile = `Accounts/${userId}/mails/${username}@${domain}`;
        fs.writeFileSync(emailFile, emailInfo);

        return {
            success: true,
            email: `${username}@${domain}`,
            username: username,
            password: password,
            token: token,
            domain: domain,
            createdAt: createdAt
        };
    } catch (error) {
        console.log('خطا در generateEmail:', error);
        return {
            success: false,
            message: '❌ خطایی رخ داد! دوباره امتحان کنید'
        };
    }
};

const loadMailBox = async (token) => {
    try {
        const headers = { Authorization: `Bearer ${token}` };
        
        const response = await axios.get('https://api.mail.tm/messages', 
            { headers, timeout: 10000 }
        );

        const messages = response.data['hydra:member'];
        const totalItems = response.data['hydra:totalItems'];

        if (totalItems === 0) {
            return {
                success: false,
                message: PERSIAN_TEXTS['inbox_empty']
            };
        }

        const inboxMessages = [];

        for (const message of messages) {
            let messageText = '';

            if (message.from && message.from.name && message.from.address) {
                messageText += PERSIAN_TEXTS['message_from']
                    .replace('{name}', message.from.name)
                    .replace('{address}', message.from.address);
            }

            if (message.subject && message.subject.trim()) {
                messageText += PERSIAN_TEXTS['message_subject']
                    .replace('{subject}', message.subject);
            } else {
                messageText += PERSIAN_TEXTS['no_subject'];
            }

            try {
                if (message.downloadUrl) {
                    const contentResponse = await axios.get(
                        `https://api.mail.tm${message.downloadUrl}`,
                        { headers, timeout: 10000 }
                    );
                    
                    const decodedContent = decodeMIME(contentResponse.data);
                    messageText += PERSIAN_TEXTS['message_content']
                        .replace('{content}', decodedContent);
                }
            } catch (contentError) {
                messageText += PERSIAN_TEXTS['empty_message'];
            }

            inboxMessages.push(messageText);
        }

        return {
            success: true,
            messages: inboxMessages
        };
    } catch (error) {
        console.log('خطا در loadMailBox:', error);
        return {
            success: false,
            message: '❌ خطایی رخ داد! دوباره امتحان کنید'
        };
    }
};

const getTotalUsers = () => {
    try {
        if (fs.existsSync('Accounts/')) {
            const dirs = fs.readdirSync('Accounts/');
            return dirs.filter(dir => 
                fs.statSync(`Accounts/${dir}`).isDirectory() &&
                !isUserBanned(dir)
            ).length;
        }
        return 0;
    } catch (error) {
        return 0;
    }
};

const getTotalEmails = () => {
    try {
        let total = 0;
        if (fs.existsSync('Accounts/')) {
            const userDirs = fs.readdirSync('Accounts/');
            
            for (const userDir of userDirs) {
                if (isUserBanned(userDir)) continue;
                
                const userMailsDir = `Accounts/${userDir}/mails/`;
                if (fs.existsSync(userMailsDir)) {
                    total += fs.readdirSync(userMailsDir).length;
                }
            }
        }
        return total;
    } catch (error) {
        return 0;
    }
};

const getTodayEmails = () => {
    try {
        const today = moment().format('YYYY-MM-DD');
        let total = 0;
        
        if (fs.existsSync('Accounts/')) {
            const userDirs = fs.readdirSync('Accounts/');
            
            for (const userDir of userDirs) {
                if (isUserBanned(userDir)) continue;
                
                const userMailsDir = `Accounts/${userDir}/mails/`;
                if (fs.existsSync(userMailsDir)) {
                    const emails = fs.readdirSync(userMailsDir);
                    
                    for (const email of emails) {
                        try {
                            const emailPath = `${userMailsDir}${email}`;
                            const content = fs.readFileSync(emailPath, 'utf8');
                            const lines = content.split('\n');
                            
                            if (lines.length >= 4) {
                                const createdLine = lines[3];
                                if (createdLine.includes('account_creat:')) {
                                    const createdDate = createdLine.split(':')[1].trim().split(' ')[0];
                                    if (createdDate === today) {
                                        total++;
                                    }
                                }
                            }
                        } catch (e) {
                            continue;
                        }
                    }
                }
            }
        }
        return total;
    } catch (error) {
        return 0;
    }
};

const getUserList = () => {
    try {
        const users = [];
        if (fs.existsSync('Accounts/')) {
            const userDirs = fs.readdirSync('Accounts/');
            
            for (const userId of userDirs) {
                if (fs.statSync(`Accounts/${userId}`).isDirectory()) {
                    const stats = getUserStats(userId);
                    users.push({
                        id: userId,
                        name: stats.name || 'ناشناس',
                        join_date: stats.join_date,
                        email_count: stats.total_emails,
                        banned: isUserBanned(userId)
                    });
                }
            }
        }
        return users;
    } catch (error) {
        return [];
    }
};

const createBackup = () => {
    try {
        const timestamp = moment().format('YYYY-MM-DD_HH-mm-ss');
        const backupDir = `Backups/backup_${timestamp}`;
        
        fs.mkdirSync(backupDir, { recursive: true });
        
        if (fs.existsSync('Accounts/')) {
            fs.cpSync('Accounts/', `${backupDir}/Accounts/`, { recursive: true });
        }
        
        if (fs.existsSync(SETTINGS_FILE)) {
            fs.copyFileSync(SETTINGS_FILE, `${backupDir}/settings.json`);
        }
        
        if (fs.existsSync('BannedUsers/list.json')) {
            fs.copyFileSync('BannedUsers/list.json', `${backupDir}/banned.json`);
        }
        
        return `${backupDir}`;
    } catch (error) {
        console.log('خطا در ایجاد پشتیبان:', error);
        return null;
    }
};

const createPersianKeyboard = () => ({
    inline_keyboard: [
        [
            { text: "🔮 ایمیل جدید", callback_data: "NewEmail", style: "success" },
            { text: "📬 لیست ایمیل‌ها", callback_data: "EmailList" }
        ],
        [
            { text: "📩 صندوق ورودی", callback_data: "EMailBoxMenu", style: "primary" },
            { text: "🗑️ حذف ایمیل", callback_data: "DelEMailMenu", style: "danger" }
        ],
        [
            { text: "📊 آمار", callback_data: "UserStats" },
            { text: "🔙 بازگشت", callback_data: "BackToStart" }
        ]
    ]
});

const createAdminKeyboard = () => ({
    inline_keyboard: [
        [
            { text: "📊 آمار کلی", callback_data: "AdminStats", style: "primary" },
            { text: "📢 ارسال پیام", callback_data: "AdminBroadcast" }
        ],
        [
            { text: "👥 مدیریت کاربران", callback_data: "AdminUsers" },
            { text: "⚙️ تنظیمات", callback_data: "AdminSettings" }
        ],
        [
            { text: "🔙 بازگشت", callback_data: "BackToStart" }
        ]
    ]
});

const createAdminUsersKeyboard = () => ({
    inline_keyboard: [
        [
            { text: "📋 لیست کاربران", callback_data: "AdminUserList" },
            { text: "🔍 اطلاعات کاربر", callback_data: "AdminUserInfo" }
        ],
        [
            { text: "🚫 مسدود کردن", callback_data: "AdminUserBan", style: "danger" },
            { text: "✅ آزاد کردن", callback_data: "AdminUserUnban", style: "success" }
        ],
        [
            { text: "🔙 بازگشت", callback_data: "AdminPanel" }
        ]
    ]
});

const createAdminSettingsKeyboard = () => {
    const maintenanceStatus = BOT_SETTINGS.maintenance ? "🟢 روشن" : "🔴 خاموش";
    const forceJoinStatus = BOT_SETTINGS.force_join ? "🟢 روشن" : "🔴 خاموش";
    
    return {
        inline_keyboard: [
            [
                { 
                    text: `🔧 حالت تعمیر ${maintenanceStatus}`, 
                    callback_data: "AdminMaintenanceToggle",
                    style: BOT_SETTINGS.maintenance ? "danger" : "success"
                }
            ],
            [
                { 
                    text: `📢 عضویت اجباری ${forceJoinStatus}`, 
                    callback_data: "AdminForceJoinToggle",
                    style: BOT_SETTINGS.force_join ? "danger" : "success"
                }
            ],
            [
                { text: "📢 تنظیم کانال", callback_data: "AdminSetChannel" }
            ],
            [
                { text: "📊 تنظیم محدودیت‌ها", callback_data: "AdminLimits" },
                { text: "💾 پشتیبان‌گیری", callback_data: "AdminBackup", style: "primary" }
            ],
            [
                { text: "🔙 بازگشت", callback_data: "AdminPanel" }
            ]
        ]
    };
};

const waitingFor = new Map();

bot.onText(/\/start|\/restart/, async (msg) => {
    try {
        const userId = msg.from.id;
        const userName = msg.from.first_name;
        
        if (BOT_SETTINGS.maintenance && !isAdmin(userId)) {
            bot.sendMessage(msg.chat.id, 
                "🔧 ربات در حال تعمیر است\nلطفاً بعداً تلاش کنید",
                { parse_mode: 'HTML' }
            );
            return;
        }
        
        if (isUserBanned(userId)) {
            bot.sendMessage(msg.chat.id, 
                "🚫 شما از ربات مسدود شده‌اید",
                { parse_mode: 'HTML' }
            );
            return;
        }
        
        if (!isAdmin(userId) && BOT_SETTINGS.force_join) {
            const isMember = await checkChannelMembership(userId);
            if (!isMember) {
                const channelLink = BOT_SETTINGS.channel_username ? 
                    `@${BOT_SETTINGS.channel_username.replace('@', '')}` : 
                    BOT_SETTINGS.channel_id;
                    
                bot.sendMessage(msg.chat.id, 
                    PERSIAN_TEXTS['force_join_message'].replace('{channel}', channelLink),
                    { parse_mode: 'HTML' }
                );
                return;
            }
        }
        
        updateUserStats(userId, 'activity', userName);
        ensureDirectories();
        
        let welcomeText = PERSIAN_TEXTS['welcome_new'].replace('{name}', userName);
        const userDir = `Accounts/${userId}`;
        
        if (fs.existsSync(userDir)) {
            welcomeText = PERSIAN_TEXTS['welcome_back'].replace('{name}', userName);
        } else {
            fs.mkdirSync(`${userDir}/mails/`, { recursive: true });
        }
        
        const keyboard = {
            inline_keyboard: [
                [{ text: "🔮 منوی اصلی", callback_data: "MainMenu", style: "primary" }],
                [{ text: "📊 آمار من", callback_data: "UserStats" }],
                [{ text: "❓ راهنما", callback_data: "HelpMenu" }]
            ]
        };
        
        if (isAdmin(userId)) {
            keyboard.inline_keyboard.push([{ text: "🔐 پنل ادمین", callback_data: "AdminPanel" }]);
        }
        
        bot.sendMessage(msg.chat.id, welcomeText, {
            reply_markup: keyboard,
            parse_mode: 'HTML'
        });
    } catch (error) {
        console.log('خطا در start:', error);
        bot.sendMessage(msg.chat.id, 'خطایی رخ داد! دوباره امتحان کن');
    }
});

bot.onText(/\/mail/, (msg) => {
    try {
        if (msg.chat.type === 'private') {
            const keyboard = createPersianKeyboard();
            bot.sendMessage(msg.chat.id, PERSIAN_TEXTS['mail_menu_title'], {
                reply_markup: keyboard,
                parse_mode: 'HTML'
            });
        }
    } catch (error) {
        console.log('خطا در mail:', error);
        bot.sendMessage(msg.chat.id, 'خطایی رخ داد! دوباره امتحان کن');
    }
});

bot.onText(/\/stats/, (msg) => {
    try {
        const userId = msg.from.id;
        const stats = getUserStats(userId);
        
        let statsText = PERSIAN_TEXTS['stats_title'] + '\n\n';
        statsText += PERSIAN_TEXTS['stats_emails'].replace('{count}', stats.total_emails) + '\n';
        statsText += PERSIAN_TEXTS['stats_created'].replace('{count}', stats.emails_created) + '\n';
        statsText += PERSIAN_TEXTS['stats_last_activity'].replace('{time}', stats.last_activity);
        
        bot.sendMessage(msg.chat.id, statsText, { parse_mode: 'HTML' });
    } catch (error) {
        console.log('خطا در stats:', error);
        bot.sendMessage(msg.chat.id, 'خطایی رخ داد! دوباره امتحان کن');
    }
});

bot.onText(/\/help/, (msg) => {
    bot.sendMessage(msg.chat.id, PERSIAN_TEXTS['help_text'], { parse_mode: 'HTML' });
});

bot.onText(/\/admin/, (msg) => {
    try {
        const userId = msg.from.id;
        
        if (!isAdmin(userId)) {
            bot.sendMessage(msg.chat.id, '❌ شما دسترسی ادمین ندارید!');
            return;
        }
        
        const keyboard = createAdminKeyboard();
        bot.sendMessage(msg.chat.id, PERSIAN_TEXTS['admin_panel_title'], {
            reply_markup: keyboard,
            parse_mode: 'HTML'
        });
    } catch (error) {
        console.log('خطا در admin:', error);
        bot.sendMessage(msg.chat.id, 'خطایی رخ داد! دوباره امتحان کن');
    }
});

bot.onText(/\/broadcast (.+)/, async (msg, match) => {
    try {
        const userId = msg.from.id;
        
        if (!isAdmin(userId)) {
            bot.sendMessage(msg.chat.id, '❌ شما دسترسی ادمین ندارید!');
            return;
        }
        
        const broadcastText = match[1];
        
        if (!broadcastText.trim()) {
            bot.sendMessage(msg.chat.id, '❌ لطفاً پیام خود را بعد از /broadcast بنویسید');
            return;
        }
        
        let sentCount = 0;
        if (fs.existsSync('Accounts/')) {
            const userDirs = fs.readdirSync('Accounts/');
            
            for (const userDir of userDirs) {
                try {
                    const userIdToSend = parseInt(userDir);
                    if (!isNaN(userIdToSend) && !isUserBanned(userIdToSend)) {
                        await bot.sendMessage(userIdToSend, `📢 پیام همگانی:\n\n${broadcastText}`, {
                            parse_mode: 'HTML'
                        });
                        sentCount++;
                        await new Promise(resolve => setTimeout(resolve, 50)); // تاخیر برای جلوگیری از محدودیت
                    }
                } catch (e) {
                    continue;
                }
            }
        }
        
        bot.sendMessage(msg.chat.id, 
            `✅ پیام با موفقیت ارسال شد\n📊 تعداد دریافت‌کنندگان: ${sentCount}`,
            { parse_mode: 'HTML' }
        );
    } catch (error) {
        console.log('خطا در broadcast:', error);
        bot.sendMessage(msg.chat.id, 'خطایی رخ داد! دوباره امتحان کن');
    }
});

bot.on('message', async (msg) => {
    try {
        if (!msg.text || msg.text.startsWith('/')) {
            return;
        }
        
        const userId = msg.from.id;
        const text = msg.text.trim();
        
        if (isAdmin(userId) && waitingFor.has(userId)) {
            const waitingData = waitingFor.get(userId);
            
            if (waitingData.type === 'channel_username') {
                if (!text.startsWith('@')) {
                    bot.sendMessage(msg.chat.id, PERSIAN_TEXTS['invalid_channel_username']);
                    return;
                }
                
                try {
                    const chat = await bot.getChat(text);
                    if (chat.type !== 'channel') {
                        bot.sendMessage(msg.chat.id, '❌ این یک کانال نیست!');
                        return;
                    }
                    
                    BOT_SETTINGS.channel_username = text;
                    waitingFor.set(userId, { type: 'channel_id', channelUsername: text });
                    
                    bot.sendMessage(msg.chat.id, PERSIAN_TEXTS['enter_channel_id']);
                    return;
                } catch (error) {
                    bot.sendMessage(msg.chat.id, '❌ کانال یافت نشد!');
                    return;
                }
            }
            
            else if (waitingData.type === 'channel_id') {
                const channelId = parseInt(text);
                if (isNaN(channelId)) {
                    bot.sendMessage(msg.chat.id, PERSIAN_TEXTS['invalid_channel_id']);
                    return;
                }
                
                BOT_SETTINGS.channel_id = channelId.toString();
                saveSettings();
                waitingFor.delete(userId);
                
                const message = PERSIAN_TEXTS['channel_set_success']
                    .replace('{username}', waitingData.channelUsername)
                    .replace('{id}', channelId);
                
                bot.sendMessage(msg.chat.id, message, { parse_mode: 'HTML' });
            }
            
            else if (waitingData.type === 'user_ban') {
                const targetUserId = parseInt(text);
                if (isNaN(targetUserId)) {
                    bot.sendMessage(msg.chat.id, '❌ آیدی کاربر نامعتبر است');
                    return;
                }
                
                if (isAdmin(targetUserId)) {
                    bot.sendMessage(msg.chat.id, '❌ نمی‌توان ادمین را مسدود کرد');
                    waitingFor.delete(userId);
                    return;
                }
                
                if (banUser(targetUserId)) {
                    bot.sendMessage(msg.chat.id, PERSIAN_TEXTS['user_banned']);
                }
                waitingFor.delete(userId);
            }
            
            else if (waitingData.type === 'user_unban') {
                const targetUserId = parseInt(text);
                if (isNaN(targetUserId)) {
                    bot.sendMessage(msg.chat.id, '❌ آیدی کاربر نامعتبر است');
                    return;
                }
                
                if (unbanUser(targetUserId)) {
                    bot.sendMessage(msg.chat.id, PERSIAN_TEXTS['user_unbanned']);
                }
                waitingFor.delete(userId);
            }
            
            else if (waitingData.type === 'user_info') {
                const targetUserId = parseInt(text);
                if (isNaN(targetUserId)) {
                    bot.sendMessage(msg.chat.id, '❌ آیدی کاربر نامعتبر است');
                    return;
                }
                
                const stats = getUserStats(targetUserId);
                const userDir = `Accounts/${targetUserId}`;
                const exists = fs.existsSync(userDir);
                
                let userInfo = PERSIAN_TEXTS['user_info']
                    .replace('{id}', targetUserId)
                    .replace('{name}', exists ? stats.name || 'ناشناس' : 'کاربر یافت نشد')
                    .replace('{join_date}', exists ? stats.join_date : 'نامشخص')
                    .replace('{email_count}', exists ? stats.total_emails : 0)
                    .replace('{status}', isUserBanned(targetUserId) ? '🚫 مسدود' : '✅ فعال');
                
                bot.sendMessage(msg.chat.id, userInfo, { parse_mode: 'HTML' });
                waitingFor.delete(userId);
            }
            
            else if (waitingData.type === 'max_emails') {
                const maxEmails = parseInt(text);
                if (isNaN(maxEmails) || maxEmails < 1 || maxEmails > 999) {
                    bot.sendMessage(msg.chat.id, '❌ تعداد نامعتبر است (1-999)');
                    return;
                }
                
                BOT_SETTINGS.max_emails_per_user = maxEmails;
                waitingFor.set(userId, { type: 'cooldown' });
                bot.sendMessage(msg.chat.id, PERSIAN_TEXTS['enter_cooldown']);
            }
            
            else if (waitingData.type === 'cooldown') {
                const cooldown = parseInt(text);
                if (isNaN(cooldown) || cooldown < 0 || cooldown > 3600) {
                    bot.sendMessage(msg.chat.id, '❌ زمان نامعتبر است (0-3600 ثانیه)');
                    return;
                }
                
                BOT_SETTINGS.cooldown_seconds = cooldown;
                saveSettings();
                waitingFor.delete(userId);
                
                bot.sendMessage(msg.chat.id, PERSIAN_TEXTS['limits_updated'], { parse_mode: 'HTML' });
            }
            
            return;
        }
        
        if (!isAdmin(userId)) {
            bot.sendMessage(msg.chat.id, '💡 از دستور /mail استفاده کن', { parse_mode: 'HTML' });
        }
        
    } catch (error) {
        console.log('خطا در پیام متنی:', error);
    }
});

bot.on('callback_query', async (callbackQuery) => {
    let callbackAnswered = false;
    const ackCallback = async (options) => {
        if (callbackAnswered) return;
        callbackAnswered = true;
        try {
            await bot.answerCallbackQuery(callbackQuery.id, options);
        } catch (ackError) {
            console.log('خطا در answerCallbackQuery:', ackError.message);
        }
    };

    try {
        const msg = callbackQuery.message;
        const userId = callbackQuery.from.id;
        const chatId = msg.chat.id;
        const messageId = msg.message_id;
        const data = callbackQuery.data;
        
        if (BOT_SETTINGS.maintenance && !isAdmin(userId)) {
            await ackCallback({
                text: '🔧 ربات در حال تعمیر است',
                show_alert: true
            });
            return;
        }
        
        if (isUserBanned(userId)) {
            await ackCallback({
                text: '🚫 شما از ربات مسدود شده‌اید',
                show_alert: true
            });
            return;
        }
        
        if (!isAdmin(userId) && BOT_SETTINGS.force_join) {
            const isMember = await checkChannelMembership(userId);
            if (!isMember) {
                const channelLink = BOT_SETTINGS.channel_username ? 
                    `@${BOT_SETTINGS.channel_username.replace('@', '')}` : 
                    BOT_SETTINGS.channel_id;
                    
                await ackCallback({
                    text: PERSIAN_TEXTS['not_member'].replace('{channel}', channelLink),
                    show_alert: true
                });
                return;
            }
        }
        
        updateUserStats(userId, 'activity', callbackQuery.from.first_name);
        
        if (data === 'NewEmail') {
            try {
                const loadingMsg = await bot.sendMessage(chatId, PERSIAN_TEXTS['generating_email'], {
                    parse_mode: 'HTML'
                });
                
                const result = await generateEmail(userId);
                
                if (result.success) {
                    updateUserStats(userId, 'email_created');
                    
                    const keyboard = {
                        inline_keyboard: [
                            [
                                { text: "📋 کپی ایمیل", copy_text: { text: result.email } },
                                { text: "📬 صندوق ورودی", callback_data: "EMailBoxMenu", style: "primary" }
                            ],
                            [
                                { text: "🔙 بازگشت", callback_data: "MainMenu" }
                            ]
                        ]
                    };
                    
                    const messageText = `${PERSIAN_TEXTS['email_created_success']}\n\n<code>${result.email}</code>`;
                    
                    await bot.editMessageText(messageText, {
                        chat_id: chatId,
                        message_id: loadingMsg.message_id,
                        reply_markup: keyboard,
                        parse_mode: 'HTML'
                    });
                } else {
                    await bot.editMessageText(result.message, {
                        chat_id: chatId,
                        message_id: loadingMsg.message_id,
                        parse_mode: 'HTML'
                    });
                }
            } catch (error) {
                console.log('خطا در NewEmail:', error);
                await ackCallback({
                    text: PERSIAN_TEXTS['error_occurred'],
                    show_alert: true
                });
            }
        }
        
        else if (data === 'MainMenu') {
            try {
                const keyboard = createPersianKeyboard();
                await bot.editMessageText(PERSIAN_TEXTS['mail_menu_title'], {
                    chat_id: chatId,
                    message_id: messageId,
                    reply_markup: keyboard,
                    parse_mode: 'HTML'
                });
            } catch (error) {
                console.log('خطا در MainMenu:', error);
            }
        }
        
        else if (data === 'HelpMenu') {
            try {
                const keyboard = {
                    inline_keyboard: [
                        [{ text: "🔮 منوی اصلی", callback_data: "MainMenu", style: "primary" }],
                        [{ text: "📊 آمار من", callback_data: "UserStats" }],
                        [{ text: "🔙 بازگشت", callback_data: "BackToStart" }]
                    ]
                };
                
                await bot.editMessageText(PERSIAN_TEXTS['help_text'], {
                    chat_id: chatId,
                    message_id: messageId,
                    reply_markup: keyboard,
                    parse_mode: 'HTML'
                });
            } catch (error) {
                console.log('خطا در HelpMenu:', error);
            }
        }
        
        else if (data === 'AdminPanel') {
            try {
                if (!isAdmin(userId)) {
                    await ackCallback({
                        text: '❌ شما دسترسی ادمین ندارید!',
                        show_alert: true
                    });
                    return;
                }
                
                const keyboard = createAdminKeyboard();
                await bot.editMessageText(PERSIAN_TEXTS['admin_panel_title'], {
                    chat_id: chatId,
                    message_id: messageId,
                    reply_markup: keyboard,
                    parse_mode: 'HTML'
                });
            } catch (error) {
                console.log('خطا در AdminPanel:', error);
            }
        }
        
        else if (data === 'BackToStart') {
            try {
                const userName = callbackQuery.from.first_name;
                const welcomeText = PERSIAN_TEXTS['welcome_back'].replace('{name}', userName);
                
                const keyboard = {
                    inline_keyboard: [
                        [{ text: "🔮 منوی اصلی", callback_data: "MainMenu", style: "primary" }],
                        [{ text: "📊 آمار من", callback_data: "UserStats" }],
                        [{ text: "❓ راهنما", callback_data: "HelpMenu" }]
                    ]
                };
                
                if (isAdmin(userId)) {
                    keyboard.inline_keyboard.push([{ text: "🔐 پنل ادمین", callback_data: "AdminPanel" }]);
                }
                
                await bot.editMessageText(welcomeText, {
                    chat_id: chatId,
                    message_id: messageId,
                    reply_markup: keyboard,
                    parse_mode: 'HTML'
                });
            } catch (error) {
                console.log('خطا در BackToStart:', error);
            }
        }
        
        else if (data === 'EmailList') {
            try {
                ensureDirectories();
                const userMailsDir = `Accounts/${userId}/mails/`;
                let keyboard = { inline_keyboard: [] };
                
                if (fs.existsSync(userMailsDir)) {
                    const mails = fs.readdirSync(userMailsDir).sort();
                    
                    for (const mail of mails) {
                        keyboard.inline_keyboard.push([
                            { text: `📧 ${mail}`, callback_data: `MailInfo_${mail}` }
                        ]);
                    }
                }
                
                const hasEmailList = keyboard.inline_keyboard.length > 0;
                keyboard.inline_keyboard.push([{ text: "🔙 بازگشت", callback_data: "MainMenu" }]);
                
                if (!hasEmailList) {
                    await bot.sendMessage(chatId, PERSIAN_TEXTS['no_emails'], {
                        reply_markup: keyboard,
                        parse_mode: 'HTML'
                    });
                } else {
                    await bot.sendMessage(chatId, PERSIAN_TEXTS['email_list_title'], {
                        reply_markup: keyboard,
                        parse_mode: 'HTML'
                    });
                }
                
                await ackCallback();
            } catch (error) {
                console.log('خطا در EmailList:', error);
            }
        }
        
        else if (data.startsWith('MailInfo_')) {
            try {
                const mail = data.slice('MailInfo_'.length);
                const filePath = `Accounts/${userId}/mails/${mail}`;
                
                if (fs.existsSync(filePath)) {
                    const content = fs.readFileSync(filePath, 'utf8');
                    const lines = content.split('\n');
                    
                    const infos = lines.map(line => {
                        const parts = line.split(':');
                        return parts.length > 1 ? parts[1].trim() : '';
                    });
                    
                    let infoText = PERSIAN_TEXTS['email_info_title'] + '\n\n';
                    infoText += PERSIAN_TEXTS['email_info_username'].replace('{username}', infos[0]) + '\n';
                    infoText += PERSIAN_TEXTS['email_info_password'].replace('{password}', infos[1]) + '\n';
                    infoText += PERSIAN_TEXTS['email_info_token'].replace('{token}', infos[2].substring(0, 20)) + '\n';
                    infoText += PERSIAN_TEXTS['email_info_created'].replace('{date}', infos[3]) + '\n';
                    infoText += PERSIAN_TEXTS['email_info_domain'].replace('{domain}', infos[4]);
                    
                    await ackCallback({
                        text: infoText,
                        show_alert: true
                    });
                }
            } catch (error) {
                console.log('خطا در MailInfo:', error);
            }
        }
        
        else if (data === 'EMailBoxMenu') {
            try {
                ensureDirectories();
                const userMailsDir = `Accounts/${userId}/mails/`;
                let keyboard = { inline_keyboard: [] };
                let hasMails = false;
                
                if (fs.existsSync(userMailsDir)) {
                    const mails = fs.readdirSync(userMailsDir).sort();
                    hasMails = mails.length > 0;
                    
                    for (const mail of mails) {
                        keyboard.inline_keyboard.push([
                            { text: `📧 ${mail}`, callback_data: `EMailBox_${mail}` }
                        ]);
                    }
                }
                
                keyboard.inline_keyboard.push([{ text: "🔙 بازگشت", callback_data: "MainMenu" }]);
                
                const menuText = hasMails ? 
                    "📬 ایمیل مورد نظر را انتخاب کن تا صندوق ورودی را ببینی" : 
                    PERSIAN_TEXTS['no_emails'];
                
                await bot.sendMessage(chatId, menuText, {
                    reply_markup: keyboard,
                    parse_mode: 'HTML'
                });
            } catch (error) {
                console.log('خطا در EMailBoxMenu:', error);
                await ackCallback({
                    text: PERSIAN_TEXTS['error_occurred'],
                    show_alert: true
                });
            }
        }
        
        else if (data.startsWith('EMailBox_')) {
            try {
                const mail = data.slice('EMailBox_'.length);
                const filePath = `Accounts/${userId}/mails/${mail}`;
                
                const retryKeyboard = {
                    inline_keyboard: [
                        [{ text: "🔄 تلاش مجدد", callback_data: `EMailBox_${mail}`, style: "primary" }],
                        [{ text: "🔙 بازگشت", callback_data: "EMailBoxMenu" }]
                    ]
                };
                
                if (!fs.existsSync(filePath)) {
                    await bot.sendMessage(chatId, "❌ این ایمیل یافت نشد! ممکن است حذف شده باشد.", {
                        reply_markup: { inline_keyboard: [[{ text: "🔙 بازگشت", callback_data: "EMailBoxMenu" }]] },
                        parse_mode: 'HTML'
                    });
                    return;
                }
                
                const content = fs.readFileSync(filePath, 'utf8');
                const lines = content.split('\n');
                
                let token = '';
                for (const line of lines) {
                    if (line.startsWith('account_token:')) {
                        token = line.split(':')[1].trim();
                        break;
                    }
                }
                
                if (!token) {
                    await bot.sendMessage(chatId, "❌ اطلاعات این ایمیل ناقص است و قابل خواندن نیست.", {
                        reply_markup: { inline_keyboard: [[{ text: "🔙 بازگشت", callback_data: "EMailBoxMenu" }]] },
                        parse_mode: 'HTML'
                    });
                    return;
                }
                
                const result = await loadMailBox(token);
                
                if (!result.success) {
                    await bot.sendMessage(chatId, `${PERSIAN_TEXTS['inbox_empty']}\n\n📧 <code>${mail}</code>`, {
                        reply_markup: retryKeyboard,
                        parse_mode: 'HTML'
                    });
                    return;
                }
                
                await bot.sendMessage(chatId, PERSIAN_TEXTS['attachment_support'], {
                    parse_mode: 'HTML'
                });
                
                for (const message of result.messages) {
                    await bot.sendMessage(chatId, message, {
                        parse_mode: 'HTML'
                    });
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
            } catch (error) {
                console.log('خطا در EMailBox:', error);
                await ackCallback({
                    text: PERSIAN_TEXTS['error_occurred'],
                    show_alert: true
                });
            }
        }
        
        else if (data === 'DelEMailMenu') {
            try {
                ensureDirectories();
                const userMailsDir = `Accounts/${userId}/mails/`;
                let keyboard = { inline_keyboard: [] };
                let hasMails = false;
                
                if (fs.existsSync(userMailsDir)) {
                    const mails = fs.readdirSync(userMailsDir).sort();
                    hasMails = mails.length > 0;
                    
                    for (const mail of mails) {
                        keyboard.inline_keyboard.push([
                            { text: `📧 ${mail}`, callback_data: `DeleteMail_${mail}` }
                        ]);
                    }
                }
                
                if (hasMails) {
                    keyboard.inline_keyboard.push([
                        { text: "⚠️ حذف همه", callback_data: "DelAllMails", style: "danger" }
                    ]);
                }
                keyboard.inline_keyboard.push([{ text: "🔙 بازگشت", callback_data: "MainMenu" }]);
                
                const menuText = hasMails ? 
                    "🗑️ ایمیل مورد نظر را برای حذف انتخاب کن\n⚠️ این عملیات قابل بازگشت نیست" : 
                    PERSIAN_TEXTS['no_emails'];
                
                await bot.sendMessage(chatId, menuText,
                    { reply_markup: keyboard, parse_mode: 'HTML' }
                );
            } catch (error) {
                console.log('خطا در DelEMailMenu:', error);
            }
        }
        
        else if (data.startsWith('DeleteMail_')) {
            try {
                const mail = data.slice('DeleteMail_'.length);
                const keyboard = {
                    inline_keyboard: [
                        [{ text: "⚠️ حذف", callback_data: `DeleteYes_${mail}`, style: "danger" }],
                        [{ text: "❌ لغو", callback_data: `DeleteNo_${mail}` }]
                    ]
                };
                
                await bot.sendMessage(chatId, 
                    `${PERSIAN_TEXTS['delete_confirm']}\n\n📧 ${mail}`,
                    { reply_markup: keyboard, parse_mode: 'HTML' }
                );
            } catch (error) {
                console.log('خطا در DeleteMail:', error);
            }
        }
        
        else if (data.startsWith('DeleteYes_')) {
            try {
                const mail = data.slice('DeleteYes_'.length);
                const filePath = `Accounts/${userId}/mails/${mail}`;
                
                if (fs.existsSync(filePath)) {
                    fs.unlinkSync(filePath);
                    await ackCallback({
                        text: PERSIAN_TEXTS['email_deleted'],
                        show_alert: true
                    });
                } else {
                    await ackCallback({
                        text: 'این ایمیل وجود ندارد!',
                        show_alert: true
                    });
                }
                
                await bot.deleteMessage(chatId, messageId);
            } catch (error) {
                console.log('خطا در DeleteYes:', error);
            }
        }
        
        else if (data.startsWith('DeleteNo_')) {
            try {
                await ackCallback({
                    text: PERSIAN_TEXTS['operation_cancelled'],
                    show_alert: true
                });
                await bot.deleteMessage(chatId, messageId);
            } catch (error) {
                console.log('خطا در DeleteNo:', error);
            }
        }
        
        else if (data === 'DelAllMails') {
            try {
                const keyboard = {
                    inline_keyboard: [
                        [{ text: "⚠️ حذف همه", callback_data: "DeleteAll_Yes", style: "danger" }],
                        [{ text: "❌ لغو", callback_data: "DeleteNo_" }]
                    ]
                };
                
                await bot.sendMessage(chatId, PERSIAN_TEXTS['delete_all_confirm'], {
                    reply_markup: keyboard,
                    parse_mode: 'HTML'
                });
            } catch (error) {
                console.log('خطا در DelAllMails:', error);
            }
        }
        
        else if (data === 'DeleteAll_Yes') {
            try {
                const userMailsDir = `Accounts/${userId}/mails/`;
                if (fs.existsSync(userMailsDir)) {
                    const mails = fs.readdirSync(userMailsDir);
                    for (const mail of mails) {
                        try {
                            fs.unlinkSync(`${userMailsDir}${mail}`);
                        } catch (e) {
                            continue;
                        }
                    }
                }
                
                await ackCallback({
                    text: PERSIAN_TEXTS['all_emails_deleted'],
                    show_alert: true
                });
                
                await bot.deleteMessage(chatId, messageId);
            } catch (error) {
                console.log('خطا در DeleteAll_Yes:', error);
            }
        }
        
        else if (data === 'UserStats') {
            try {
                const stats = getUserStats(userId);
                
                let statsText = PERSIAN_TEXTS['stats_title'] + '\n\n';
                statsText += PERSIAN_TEXTS['stats_emails'].replace('{count}', stats.total_emails) + '\n';
                statsText += PERSIAN_TEXTS['stats_created'].replace('{count}', stats.emails_created) + '\n';
                statsText += PERSIAN_TEXTS['stats_last_activity'].replace('{time}', stats.last_activity);
                
                const keyboard = {
                    inline_keyboard: [
                        [{ text: "🔮 منوی اصلی", callback_data: "MainMenu", style: "primary" }],
                        [{ text: "📊 بروزرسانی آمار", callback_data: "UserStats" }],
                        [{ text: "🔙 بازگشت", callback_data: "BackToStart" }]
                    ]
                };
                
                await bot.editMessageText(statsText, {
                    chat_id: chatId,
                    message_id: messageId,
                    reply_markup: keyboard,
                    parse_mode: 'HTML'
                });
            } catch (error) {
                console.log('خطا در UserStats:', error);
            }
        }
        
        else if (data === 'AdminStats') {
            try {
                if (!isAdmin(userId)) {
                    await ackCallback({
                        text: '❌ شما دسترسی ادمین ندارید!',
                        show_alert: true
                    });
                    return;
                }
                
                const totalUsers = getTotalUsers();
                const totalEmails = getTotalEmails();
                const todayEmails = getTodayEmails();
                const bannedCount = bannedUsers.size;
                const maintenanceStatus = BOT_SETTINGS.maintenance ? "🟢 روشن" : "🔴 خاموش";
                const forceJoinStatus = BOT_SETTINGS.force_join ? "🟢 روشن" : "🔴 خاموش";
                
                let statsText = PERSIAN_TEXTS['admin_stats_title'] + '\n\n';
                statsText += PERSIAN_TEXTS['admin_stats_users'].replace('{count}', totalUsers) + '\n';
                statsText += PERSIAN_TEXTS['admin_stats_emails'].replace('{count}', totalEmails) + '\n';
                statsText += PERSIAN_TEXTS['admin_stats_today'].replace('{count}', todayEmails) + '\n';
                statsText += PERSIAN_TEXTS['admin_stats_banned'].replace('{count}', bannedCount) + '\n';
                statsText += PERSIAN_TEXTS['admin_stats_maintenance'].replace('{status}', maintenanceStatus) + '\n';
                statsText += PERSIAN_TEXTS['admin_stats_force_join'].replace('{status}', forceJoinStatus) + '\n';
                statsText += PERSIAN_TEXTS['admin_stats_online'];
                
                await ackCallback({
                    text: statsText,
                    show_alert: true
                });
            } catch (error) {
                console.log('خطا در AdminStats:', error);
            }
        }
        
        else if (data === 'AdminBroadcast') {
            try {
                if (!isAdmin(userId)) {
                    await ackCallback({
                        text: '❌ شما دسترسی ادمین ندارید!',
                        show_alert: true
                    });
                    return;
                }
                
                await ackCallback({
                    text: '📢 از دستور /broadcast استفاده کنید\n\nمثال:\n/broadcast سلام به همه کاربران!',
                    show_alert: true
                });
            } catch (error) {
                console.log('خطا در AdminBroadcast:', error);
            }
        }
        
        else if (data === 'AdminUsers') {
            try {
                if (!isAdmin(userId)) {
                    await ackCallback({
                        text: '❌ شما دسترسی ادمین ندارید!',
                        show_alert: true
                    });
                    return;
                }
                
                const keyboard = createAdminUsersKeyboard();
                await bot.editMessageText(PERSIAN_TEXTS['admin_user_management'], {
                    chat_id: chatId,
                    message_id: messageId,
                    reply_markup: keyboard,
                    parse_mode: 'HTML'
                });
            } catch (error) {
                console.log('خطا در AdminUsers:', error);
            }
        }
        
        else if (data === 'AdminUserList') {
            try {
                if (!isAdmin(userId)) {
                    await ackCallback({
                        text: '❌ شما دسترسی ادمین ندارید!',
                        show_alert: true
                    });
                    return;
                }
                
                const users = getUserList();
                let userListText = "📋 لیست کاربران:\n\n";
                
                users.slice(0, 20).forEach((user, index) => {
                    userListText += `${index + 1}. ${user.name} (${user.id})\n`;
                    userListText += `   📧 ایمیل‌ها: ${user.email_count}\n`;
                    userListText += `   📅 عضویت: ${user.join_date}\n`;
                    userListText += `   وضعیت: ${user.banned ? '🚫' : '✅'}\n\n`;
                });
                
                if (users.length > 20) {
                    userListText += `\n📊 و ${users.length - 20} کاربر دیگر...`;
                }
                
                await bot.sendMessage(chatId, userListText, { parse_mode: 'HTML' });
            } catch (error) {
                console.log('خطا در AdminUserList:', error);
            }
        }
        
        else if (data === 'AdminUserInfo') {
            try {
                if (!isAdmin(userId)) {
                    await ackCallback({
                        text: '❌ شما دسترسی ادمین ندارید!',
                        show_alert: true
                    });
                    return;
                }
                
                waitingFor.set(userId, { type: 'user_info' });
                await bot.sendMessage(chatId, PERSIAN_TEXTS['enter_user_id']);
            } catch (error) {
                console.log('خطا در AdminUserInfo:', error);
            }
        }
        
        else if (data === 'AdminUserBan') {
            try {
                if (!isAdmin(userId)) {
                    await ackCallback({
                        text: '❌ شما دسترسی ادمین ندارید!',
                        show_alert: true
                    });
                    return;
                }
                
                waitingFor.set(userId, { type: 'user_ban' });
                await bot.sendMessage(chatId, PERSIAN_TEXTS['enter_user_id']);
            } catch (error) {
                console.log('خطا در AdminUserBan:', error);
            }
        }
        
        else if (data === 'AdminUserUnban') {
            try {
                if (!isAdmin(userId)) {
                    await ackCallback({
                        text: '❌ شما دسترسی ادمین ندارید!',
                        show_alert: true
                    });
                    return;
                }
                
                waitingFor.set(userId, { type: 'user_unban' });
                await bot.sendMessage(chatId, PERSIAN_TEXTS['enter_user_id']);
            } catch (error) {
                console.log('خطا در AdminUserUnban:', error);
            }
        }
        
        else if (data === 'AdminSettings') {
            try {
                if (!isAdmin(userId)) {
                    await ackCallback({
                        text: '❌ شما دسترسی ادمین ندارید!',
                        show_alert: true
                    });
                    return;
                }
                
                const keyboard = createAdminSettingsKeyboard();
                await bot.editMessageText(PERSIAN_TEXTS['admin_settings'], {
                    chat_id: chatId,
                    message_id: messageId,
                    reply_markup: keyboard,
                    parse_mode: 'HTML'
                });
            } catch (error) {
                console.log('خطا در AdminSettings:', error);
            }
        }
        
        else if (data === 'AdminMaintenanceToggle') {
            try {
                if (!isAdmin(userId)) {
                    await ackCallback({
                        text: '❌ شما دسترسی ادمین ندارید!',
                        show_alert: true
                    });
                    return;
                }
                
                BOT_SETTINGS.maintenance = !BOT_SETTINGS.maintenance;
                saveSettings();
                
                const statusText = BOT_SETTINGS.maintenance ? 
                    PERSIAN_TEXTS['admin_maintenance_on'] : 
                    PERSIAN_TEXTS['admin_maintenance_off'];
                
                await ackCallback({
                    text: statusText,
                    show_alert: true
                });
                
                const keyboard = createAdminSettingsKeyboard();
                await bot.editMessageReplyMarkup(keyboard, {
                    chat_id: chatId,
                    message_id: messageId
                });
            } catch (error) {
                console.log('خطا در AdminMaintenanceToggle:', error);
            }
        }
        
        else if (data === 'AdminForceJoinToggle') {
            try {
                if (!isAdmin(userId)) {
                    await ackCallback({
                        text: '❌ شما دسترسی ادمین ندارید!',
                        show_alert: true
                    });
                    return;
                }
                
                BOT_SETTINGS.force_join = !BOT_SETTINGS.force_join;
                saveSettings();
                
                const statusText = BOT_SETTINGS.force_join ? 
                    PERSIAN_TEXTS['admin_force_join_on'] : 
                    PERSIAN_TEXTS['admin_force_join_off'];
                
                await ackCallback({
                    text: statusText,
                    show_alert: true
                });
                
                const keyboard = createAdminSettingsKeyboard();
                await bot.editMessageReplyMarkup(keyboard, {
                    chat_id: chatId,
                    message_id: messageId
                });
            } catch (error) {
                console.log('خطا در AdminForceJoinToggle:', error);
            }
        }
        
        else if (data === 'AdminSetChannel') {
            try {
                if (!isAdmin(userId)) {
                    await ackCallback({
                        text: '❌ شما دسترسی ادمین ندارید!',
                        show_alert: true
                    });
                    return;
                }
                
                waitingFor.set(userId, { type: 'channel_username' });
                await bot.sendMessage(chatId, PERSIAN_TEXTS['enter_channel_username']);
            } catch (error) {
                console.log('خطا در AdminSetChannel:', error);
            }
        }
        
        else if (data === 'AdminLimits') {
            try {
                if (!isAdmin(userId)) {
                    await ackCallback({
                        text: '❌ شما دسترسی ادمین ندارید!',
                        show_alert: true
                    });
                    return;
                }
                
                waitingFor.set(userId, { type: 'max_emails' });
                await bot.sendMessage(chatId, PERSIAN_TEXTS['enter_max_emails']);
            } catch (error) {
                console.log('خطا در AdminLimits:', error);
            }
        }
        
        else if (data === 'AdminBackup') {
            try {
                if (!isAdmin(userId)) {
                    await ackCallback({
                        text: '❌ شما دسترسی ادمین ندارید!',
                        show_alert: true
                    });
                    return;
                }
                
                const backupPath = createBackup();
                if (backupPath) {
                    await ackCallback({
                        text: PERSIAN_TEXTS['backup_created'] + `\n📍 مسیر: ${backupPath}`,
                        show_alert: true
                    });
                } else {
                    await ackCallback({
                        text: '❌ خطا در ایجاد پشتیبان',
                        show_alert: true
                    });
                }
            } catch (error) {
                console.log('خطا در AdminBackup:', error);
            }
        }
        
        // اطمینان از پاسخ به callback در صورتی که هیچ‌کدام از حالت‌های بالا پاسخ نداده باشند
        await ackCallback();
        
    } catch (error) {
        console.log('خطای کلی در callback:', error);
        await ackCallback({
            text: PERSIAN_TEXTS['error_occurred'],
            show_alert: true
        });
    }
});

bot.on('polling_error', (error) => {
    console.log(`خطای polling: ${error.code} - ${error.message}`);
});

console.log('🚀 راه‌اندازی ربات...');
console.log('📧 ربات ایمیل موقت آماده است!');

loadSettings();
loadBannedUsers();
ensureDirectories();

bot.startPolling();