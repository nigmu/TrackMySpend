plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.trackmyspend.companion"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.trackmyspend.companion"
        minSdk = 26
        targetSdk = 34
        versionCode = 3
        versionName = "1.2"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
        buildConfig = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.viewpager2:viewpager2:1.0.0")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("androidx.fragment:fragment-ktx:1.6.2")
    implementation("androidx.coordinatorlayout:coordinatorlayout:1.2.0")
    implementation("androidx.work:work-runtime-ktx:2.9.0")
}

// After assembleDebug / assembleRelease, drop the APK where the API serves OTA files.
val companionReleasesDir =
    rootProject.projectDir.resolve("../../releases/companion").normalize().absoluteFile

afterEvaluate {
    listOf("debug", "release").forEach { buildType ->
        val capitalize = buildType.replaceFirstChar { it.uppercase() }
        val copyTask = tasks.register<Copy>("copy${capitalize}ApkToReleases") {
            from(layout.buildDirectory.dir("outputs/apk/$buildType")) {
                include("*.apk")
            }
            into(companionReleasesDir)
            rename { "companion-${android.defaultConfig.versionName}.apk" }
            doFirst { companionReleasesDir.mkdirs() }
        }
        tasks.named("assemble$capitalize").configure { finalizedBy(copyTask) }
    }
}
